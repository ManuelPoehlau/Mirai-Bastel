# AD-025 — Topology Identity, Provenance and Point Layers (ARCH-02)

**Status:** PROPOSED (2026-10-27); **revised the same day after the independent review**
[CLAUDE-001](../archive/deformation/reviews/AD-025_REVIEW_CLAUDE_001.md) (ACCEPT WITH CHANGES, no blocker; the disposition
of every finding is in §13). **IMPLEMENTED (Phase 2, 2026-10-27)** — Core layers, journal, file, origin rules, backstop and
the app gate; implementation note with the measured numbers in §14. **IMPLEMENTED (Phase 3, 2026-10-27)** — one
persistent target in the app: lifecycle, the editing view beside the base (the §11 mechanics decided in §15), the weight as
view state, the mix display, Apply transform carrying the targets; implementation note in §15. **IMPLEMENTED (Phase 5,
2026-10-27)** — topology edits while a mesh has targets: Split, Edge Connect, Loop Insert, Collapse, Extrude, the Knife
(`split_face(…, origins=…)`, the second small Core change) and mirror copy are declared, plain and symmetric; implementation
note in §16. **IMPLEMENTED (Phase 4, 2026-10-27)** — several targets per mesh, the additive mix with its drift guard,
the stage chain morph → SubD (H5b) and packed layer storage (the Core internals); implementation note in §17. Phases 6
and 7 open.
**Go for the Phase 2 Core change: Manu, 2026-10-27** ("I give the Go for the Phase 2 Core Changes"). **Go for the Phase 5
Core change (`split_face(…, origins=…)`): Manu, 2026-10-27** (given with the Phase 5 assignment). **H1–H5 and C-1 decided: Manu, 2026-10-27**
("ok ich gebe H1-H5 und C1 ein ja") — every recommended default of §10 / Kurzfassung holds; nothing is `PROVISIONAL` in §10
any more.
**Gate:** [ROADMAP ARCH-02](ROADMAP.md#arch-02--topology-identity--provenance--remapping); audit §G Phase 1.
**Mode (M5):** Discovery → decision preparation; Phases 2, 3, 4 and 5 implemented (§14–§17). Next: Phase 6 (§17.5).
**Go for the Phase 4 Core internals (packed storage behind the unchanged API): Manu, 2026-10-27** (given with the Phase 4
assignment).
**Input:** [mesh architecture audit 2026-10-27](../research/deformation/MESH_ARCHITECTURE_AUDIT_2026-10-27.md) (§C–§H and
the Phase 0 addendum). Every claim taken from it was re-verified against the code at `a53c14f` (Phase 0 merged); where
this AD differs from the audit, it says so (§1, last paragraph).
**Builds on:** AD-001 / AD-002 ([V1_CORE](V1_CORE.md)), [AD-021 §4.9](AD-021-OBJECT-COMPONENT-MODEL.md) (Mesh = rest shape;
ID-keyed deformation data lives with the Mesh), [AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) §2 H1 / §9
(journal, exactness contract), [AD-REGIONS-01](AD-REGIONS-01-FACE-REGIONS-STORAGE.md) (§1.6 inheritance, §2 whole-value
cost), [AD-SYM-03](AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) §2.5 D-b (declaration = support, fail-closed),
[AD-017](AD-017-CUT-ENGINE-CONTEXTUAL-C.md) B5 / K1 and its open point "parent corner data passed in"
([addendum](AD-017_FINAL_DECISIONS_2026-09-22.md)), [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §1, §4, §7. Supersedes the morph
part of [AD-005](AD-005-RIGGING-INTEGRATION.md) (already SUPERSEDED).
**Decided by:** Manu (H1–H5; go for the Phase 2 Core change); the Core change follows CORE_V1_FREEZE §7 (§8).
**Tags:** **[V]** verified in code at `a53c14f` · **[C]** measured in the container (Linux, Python 3.13.17; the author's
throwaway probes outside the repository, not kept) · **[R]** measured by the review CLAUDE-001 (container; probe code and
output in its appendix) · **[H]** estimate. No number here is a reference-PC number; the reference PC runs Python ≈ 2×
slower ([REFERENCE_HARDWARE](REFERENCE_HARDWARE.md) §2), and container timings varied up to ~2× between runs.

---

## 0. Decision in one screen

1. **Identity** keeps the AD-001 contract: IDs are never reused, and every ID an operation does not invalidate keeps its
   meaning.
2. **Origin is applied, not stored.** An operation that creates or merges a vertex gives it its value in every point
   layer at mutation time, from an affine combination of existing vertices. Phase 2 builds only the rules that are the
   position's own arithmetic: `split_edge` (1 − t, t), the Collapse average (`collapse_edge`, `collapse_elements`), and
   `add_vertex(position, origin=…)` for tool-built vertices (Extrude: "copy of v"). Knife interior points get their
   origin from the Knife in Phase 5 (`split_face(…, origins=…)`: barycentric weights of the triangle it hit, over the
   original face's corners); until then `split_face` with interior points refuses on a layered mesh. Nothing about an
   origin outlives the call: no provenance store, no operation log, no listener.
3. **Point layers are owned by the Mesh** and live in the existing change journal: per element for sparse edits, as one
   whole-layer record (copy-on-write) for bulk operations. Undo/Redo, rollback (Knife checkpoints, Extrude cancel, nested
   Collapse, `_mesh_transaction`) and the file come from the same mechanism as positions. Watches record which values
   changed, not their old values. A morph target is one vector layer of offsets keyed by the base's `VertexId`s (Manu's
   J-3: "relativ").
4. **Edit vs. frame change:** an edit (every component tool) changes rest positions and leaves offsets alone; a frame
   change (Apply transform, mirror copy) re-expresses the shape and maps vector values by its linear part.
5. **Fail-closed gate** over every entry point that can change or copy a mesh (commands, menu methods, the methods that
   build a mesh from another), checked per target mesh; the Core backstops by refusing a vertex without an origin.
6. **Face regions stay as they are** (inference, AD-REGIONS-01 §1.6).
7. **H1–H5 are parameters:** H1 = the gate table's content, H2 = a per-layer rule, H3 = the merge rule (average only
   until another rule is asked for), H4 = the Phase 3 editing view, H5 = the phase order. None of them blocks Phase 2.

## 1. Facts this AD relies on (re-verified at `a53c14f`; confirmed by the review, three wordings corrected)

| # | Fact | Where [V] |
|---|---|---|
| F-1 | Every `Mesh` mutation records, on first touch, before-records in every active `MeshChange`: position, edge `(v0, v1, faces)`, boundary, symmetry, regions. No origin, no operation parameters | `src/core/mesh.py:157`, `:316` |
| F-2 | Vertices are created only by `add_vertex` (`mesh.py:439`); `split_edge` (`:536`) and `split_face` (`:776`) call it internally, **after** their first mutation (`:563` before `:568`, `:865` before `:867`). On an *edited* mesh the only direct tool caller is Extrude (`extrude.py:229`); the other callers build new meshes (`scene_factory`, `object_mirror.mirror_mesh`, the SubD derived mesh `subdivision/preview.py:442`) | grep `add_vertex(` in `src/`; the only writes to `Mesh._vertices` are `:444`, `:737`, `load_state`, `_apply_records` |
| F-3 | Vertices are removed only through `_delete_vertex` (`mesh.py:733`: `collapse_edge`, Dissolve, Delete) and, for Undo / rollback / load, through `_apply_records` (`:1632`) and `load_state` | |
| F-4 | `split_edge` places the vertex at `a·(1−t) + b·t`, `(a, b)` = the edge's stored `(v0, v1)`; `collapse_edge` (`:599`) keeps `v0` at `(a + b) / 2` and deletes `v1`; `collapse_elements` (`core/operations/collapse.py:72`) chains `collapse_edge` in candidate-ID order and then sets the survivor to the centroid of the group's original positions | |
| F-5 | `split_face` deletes the parent before creating its k interior vertices at caller positions, no geometry check. Knife interior positions are ray hits on the viewport's triangles (`picking.face_hit_position`, `viewport/picking.py:287`); the viewport triangulates by ear clipping after projecting onto the **dominant axis plane** of the Newell normal (`viewport/derived.py:87`); only `FaceFrame` (`mirai/topology/face_geometry.py`) uses the true Newell plane. A closed Knife shape is two `split_face` calls, the second inside a half of the first (`knife_resolve.py`, `close_loop_with_bridges`), with bridge ends chosen by `select_bridge` | |
| F-6 | Two tools post-process positions after a primitive: the symmetric Knife replays a kept `split_edge` on the mirror edge **at t = 0.5** and then moves the vertex to the mirror position (`symmetric_knife.py:392–397`); the symmetric Collapse snaps survivors to the plane or to the mirror position (`symmetric_ops.py:330–343`). The symmetric Split / Edge Connect coordinators split at 0.5 on both sides (`symmetric_ops.py:196`) | |
| F-7 | Apply transform writes `to_world(p)` per vertex inside one `record_mesh_change` per baked object — every placed object of the selection, not only the edit object (`scene_objects.py:405`, `application.py:1872–1876`); a displacement maps by `delta_to_world = s·R·d` (`object_space.py`). Mirror copy is a menu method (`src/scene_menu.py:119`, `MIRROR_ENTRIES` → `Application.mirror_copy`, `application.py:1337`), not a command; it builds a new mesh with `H·p` and reversed winding, new dense IDs in source-ID order (`object_mirror.py:84`) | |
| F-8 | Every topology commit boundary is one journal recording: `_mesh_transaction` (`application.py:5461`), Extrude begin → commit / cancel, Knife `SessionStart` with `revert_change` checkpoints, Loop Slide and Smooth gestures, Apply transform; Collapse rolls back per group (nested). **Move / Rotate / Scale / Tweak commit `VertexTransformCommand` position snapshots** (`core/operations/transform.py:206`), not recordings — harmless for layers (positions only) | |
| F-9 | Readers of `MeshChange` internals outside the Core: `SessionStart.unchanged()` / `.state()` (`knife_resolve.py:291`, `:302`), `regions.inherit_into`. Content filters drop top-level keys ending in `_counter` (`knife_resolve.py:550` and the tests); no test pins the export key set | |
| F-10 | An edited mesh carries up to five `MeshWatch`es (render mesh `viewport/render_mesh.py:187`, two in the pick cache `mirai/viewport/picking_cache.py:135`, `:289`, SubD preview `subdivision/preview.py:289`, soft shading `soft_selection/gl_shading.py:132`; the Morph Lab adds one), plus one recording per nesting level (the operation's; Knife `SessionStart` plus one checkpoint per candidate, run or closed shape; Collapse's own group recording). Each journaled write touches every active log | |
| F-11 | Morph Lab: target = full mesh copy paired by equal IDs; any topology change switches the mix off. Manu 2026-10-17: J-3 "relativ" (the target follows later base edits), J-5 "daneben", the weight is no Undo step and not saved, picking on the rest shape "hilft" | [Morph Lab README](../../experiments/morph_lab/README.md) |
| F-12 | Triangulation is a viewport algorithm (`src/viewport/derived.py`), not a Core one | |

**Where this AD differs from the audit:** (a) the audit's Phase 5 holds all origin interpolation; this AD builds the
exact rules (edge blend, Collapse average, `add_vertex` origin) with the Core layers in Phase 2 and leaves the Knife
interior rule with the Knife in Phase 5 (§7). (b) The two position post-processors of F-6 are tool-level cases that
"covered if origin is recorded at primitive level" (audit §D) does not cover (§3, §4.4). (c) Edge Connect and Loop Insert
are midpoint splits plus `connect_vertices` [V] — one row with Split. (d) The audit's H3 alternative ("keep one point's
offset") is not a well-defined rule (§13 M-5).

## 2. The six ARCH-02 questions

**Which identities survive topology changes?** Every ID an operation does not name as invalidated, with unchanged meaning
(AD-001; each primitive's docstring states its ID continuity; per operation in §3). Undo, Redo, rollback and `load_state`
restore records and never lower a counter, so an ID that returns after Undo is the same element. Point-layer values are
keyed by `VertexId` and live and die with their vertex; they change only where an origin rule or an explicit write puts
them. References from outside the mesh, `(ObjectId, VertexId)`, are valid or dead, never wrong (AD-021 §4.5).

**When are new identities created?** Only inside the Core mutation primitives: `add_vertex`; edges in `add_face`,
`add_edge`, `_get_or_create_edge`; `add_face`; and the composites — `split_edge` +1 V +2 E, `split_face` +k V +(k+1) E
+2 F, `connect_vertices` +1 E +2 F, Dissolve +1 F per region / +1 E per removed chain, Collapse and Delete none. Tools
create IDs only through these. Undo/Redo, rollback and load create none. A new ID space is a new `Mesh` (mirror copy, OBJ
import, Add Mesh, SubD's derived mesh, `Mesh.from_state`). New with this AD: `LayerId` (§4.2), same contract.

**Can a new element record its origin?** A new or merged **vertex** gets an origin — defined by the primitive, or passed
by the tool through `add_vertex(origin=…)` and, from Phase 5, `split_face(…, origins=…)` — and the origin is **applied**
to every point layer inside the same call; it is **not recorded**: the journal records the resulting layer values like any
other write. **Edges and faces** record no origin; face data keeps the inference of AD-REGIONS-01 §1.6; an exact face
origin is available inside `split_face`, `connect_vertices` and Dissolve if a face-domain layer is ever needed (§4.5). No
element carries provenance metadata.

**Which dependent data can be invalidated?** Derived and session data — never saved, never remapped; it follows the
journal (`MeshWatch`) or is recomputed: render buffers, pick cache and screen grid, SubD derived mesh and stencils,
symmetry correspondence and completeness reports, Soft Selection weights, mask / hide sets and the selection (dead IDs
filtered), the Knife's kept-call report (one session), and from Phase 3 the evaluated (deformed) positions.

**Which dependent data must be remapped?** Persistent ID-keyed data whose meaning survives the edit: (a) **point layers**
(morph offsets now, normalized weights later), by the origin rule of the creating operation (§4.1); (b) **face regions**,
by the existing inference (unchanged); (c) the **symmetry seam**, by the coordinators' seam rules S1–S3 (unchanged). Data
held outside the mesh and keyed into it (future skin bindings, animation keys) is not remapped; a dead ID drops out.

**What minimum information must topology operations expose?** (1) Their ID-continuity contract (exists). (2) For each
vertex they create or merge, an origin applied to the layers in the same recording — inside the primitive where the rule
is the position's own arithmetic, otherwise passed by the tool (`add_vertex(origin=…)`, `split_face(…, origins=…)`).
(3) For a whole-mesh frame change, its linear map (§4.3). (4) At app level, a declaration that the resolved operation is
layer-safe (§4.4). Nothing more: no operation log, no provenance in History, no callbacks, no parameters in the journal.

## 3. Per-operation contract

All topology rows run inside one journal recording (F-8): Undo/Redo is the delta, rollback is the journal, and layer
writes made by the primitives are part of both. "Gate" = the H1 default (`PROVISIONAL`, §10).

| Operation (code path) | Keeps | Creates / invalidates | Point-layer rule | Gate |
|---|---|---|---|---|
| Split (`C`, 1 edge: `split_edge(e, 0.5)`) | both ends; both faces (boundary +1) | +1 V, +2 E / `e` | new = (1−t)·v0 + t·v1, `(v0, v1)` as stored — the position's expression (Phase 2) | **declared since Phase 5** |
| Edge Connect, Loop Insert (`split_edge(e, 0.5)` per kept edge, then `connect_vertices` per face) | edge ends; faces without a chord | per split as Split; per chord +1 E, +2 F / the face | midpoints as Split; chords none | **declared since Phase 5** |
| Vertex Connect (`connect_vertices`) | all vertices, untouched edges | +1 E, +2 F / the face | none (no vertex) | allowed |
| Knife (kept `split_edge(e, t)`, `split_face(f, a, b, positions)`; closed shape = two calls) | boundary vertices and edges of the cut faces | edge points as Split; per call k V, k+1 E, 2 F / the parent (an intermediate face is burned) | edge points (1−t, t) (Phase 2; a split of an already split piece stays linear along the original edge). Interior points: the Knife passes their origin — barycentric weights of the hit triangle over the **original** face's corners (`split_face(origins=…)`, Phase 5). Until then `split_face` with k > 0 refuses on a layered mesh. A point the run makes where it crosses itself: the blend of its segment's ends (§16). Session: `SessionStart`; a dropped candidate `revert_change`; refused commit `abandon` | **declared since Phase 5** |
| Symmetric Knife (replay of kept calls) | per side as Knife | per side as Knife | source side as Knife. Mirror side (Phase 5; before it: split at 0.5, then the snap, F-6): `split_edge` at the mapped t (t or 1−t by the mirror edge's stored orientation), then the position snap; interior origins mirrored through the vertex map (the source triangle's weights on the mirror corners, §16) | **declared since Phase 5** |
| Symmetric Split / Edge Connect / Collapse / removal / Cap / Extrude coordinators | per side | per side | each side through its own primitive call; mirror values equal the mirrored source values up to rounding (positions keep their exact snap; values need none; the Collapse snap does not affect the average) | as the plain operation |
| Extrude (tool: `add_vertex` copies, walls/caps `add_face`, `remove_face`, `delete_edges` of orphans) | everything outside the region; region boundary vertices (wall bases) | +1 V per region vertex, walls, caps / region faces, inner edges, inner vertices | cap vertex = copy of its source, `origin=((v, 1.0),)`; the drag then moves positions only | **declared since Phase 5** |
| Collapse V/E/F (`collapse_elements`) | one survivor per group | other group vertices, inner edges, degenerate faces / none created | survivor = component mean of the group's **original** values, `_centroid`'s arithmetic (H3, Phase 2) | **declared since Phase 5** |
| `collapse_edge` (primitive) | `v0` | `v1`, `e`, degenerate faces | (a + b)/2, the position's expression | — |
| Dissolve V/E/F (± cleanup), Delete V/E/F, Cap | everything not removed | deletions; Dissolve +1 F per region, +1 E per chain; Cap +1 F per loop | none created; values of removed vertices are deleted (journaled) | allowed |
| Move / Rotate / Scale, Tweak, Soft, Loop Slide, Smooth, Relax, Re-Symmetrize | all | positions only | untouched (edit rule, §4.3); Re-Symmetrize therefore leaves targets as they were | allowed |
| Apply transform (`apply_placement`, composite command, every baked object) | all | positions `p → to_world(p)` | vector `v → s·R·v`; weights unchanged; identity placement: nothing | **declared since Phase 3** (`apply_placement` maps, §15) |
| Clear transform, object W/E/R in `4` | all | placement only | none | allowed |
| Mirror copy (menu method `mirror_copy` → `mirror_mesh`) | source unchanged | new mesh, new IDs (dense, source-ID order) | each layer copied through the index map, vector `v → H·v` (bit-exact for axis planes); the copy's layers are its own (no link to the source's, §11) | **declared since Phase 5** |
| Morph Lab send (`M`, `morph_bridge`) | source unchanged | a file copy of the mesh state | the copy carries the layers (the Lab ignores them) | allowed |
| Undo / Redo (`apply_delta`) | exact | — | the delta's records | — |
| Load scene · OBJ import · Add Mesh · SubD derived mesh | new ID spaces | — | the scene file restores layers; the others carry none | — |
| OBJ export | — | — | rest shape only | — |

## 4. Mechanism

### 4.1 Vertex origin

`VertexOrigin = tuple[tuple[VertexId, float], ...]`: live source vertices with finite weights, |Σw − 1| ≤ 1e-9; `()` means
"no source" (explicit). It exists only during the call. Per layer, a new or merged vertex gets the kind's combination of
its sources' values (an absent value counts as the kind's default) — unless the layer's `new_point` rule (H2) is `"zero"`,
then nothing is stored. A result equal to the default is not stored (canonical form, §4.2). Origins are computed and
validated **before the first mutation** of the primitive (F-2: today `split_edge` / `split_face` mutate before
`add_vertex`), so a refusal leaves the mesh and the counters unchanged.

**Phase 2 (Core):**

- **`split_edge(e, t)`:** origin `((v0, 1−t), (v1, t))` with the stored ends; vector values use the position's own
  expression `a·(1−t) + b·t` per component. Total (never refuses because of layers). Cost [C]: +0.01 / +0.04–0.06 ms per
  split with 10 / 50 layers at 15 % occupancy (0.024–0.028 ms without layers, 20k and 87.5k alike).
- **`collapse_edge(e)`:** survivor = (a + b)/2 per component (the position's expression); then `v1`'s values go with `v1`.
- **`collapse_elements`:** after the chain, each merging group's survivor gets the component mean of the group's
  **original** values, captured before the chain with `_centroid`'s arithmetic (the chain's pairwise averages are
  overwritten, as the positions are).
- **`add_vertex(position, origin=None)`:** without layers `origin` is ignored and behaviour is unchanged. With layers an
  origin is required: `None` raises `MeshError` before any mutation, counters unchanged (the Core backstop, §4.4); `()`
  stores defaults; otherwise validated and applied.
- **`split_face(f, a, b, positions)`:** k = 0 has no layer effect. **k > 0 on a layered mesh raises `MeshError` before the
  first mutation** — unreachable through the gate (H1 locks the Knife), and no Core rule is built before its consumer
  (CORE_V1_FREEZE §1, §13 M-4).
- **`_delete_vertex(v)`:** deletes `v`'s values in every layer, journaled (invariant L1).
- No layer effect: `connect_vertices`, `add_face`, `add_edge`, `remove_face`, the face/edge part of Dissolve,
  `set_vertex_position`.

**Phase 5 (with the Knife wiring; a second, additive Core change — built 2026-10-27, §16):** `split_face(…, origins=None)` — one `VertexOrigin`
per interior position, required for k > 0 on a layered mesh, any live vertices as sources. The Knife computes each
interior point's origin when the point is picked: the barycentric weights of the triangle `face_hit_position` hit, over
that triangle's corners — corners of the **original** face, which stay live for the whole session because `split_face`
keeps every boundary vertex. The record travels with the path point to the resolver (which stays camera-free). This
makes the value independent of how the resolver decomposes a cut and puts the new point exactly on the target's drawn
surface; the Core never triangulates. Evidence that decided it [R, §13 M-1]:

- mean value coordinates (MVC) per call over the *current* parent, the first draft's rule: a closed Knife shape differs
  from one interpolation over the original face by 2.4–10.4 % of the value spread with the resolver's own `select_bridge`,
  up to 21–30 % with opposite-corner bridges (the author's first figure of ≤ 3 % fixed one bridge geometry) — and the
  result would change whenever the bridge rule changes;
- an MVC-placed point lies up to 75 % of the offset magnitude off the target's drawn surface on a planar face with
  non-affine corner offsets; barycentric on the drawn triangle lies on it (≤ 1e-13); for smooth Gaussian bumps on
  gollum_20k the MVC deviation is small (p99 0.1–3.3 %, max 0.8–7.6 % of the amplitude);
- MVC on warped faces, in a stable metric (error / (|∇f| · face size)): gollum_20k p50 0.18 %, p99 2.4 %, max 39 %;
  warp distribution p50 0.36 %, p99 3.9 %, max 21 % [C] [R]. MVC stays the documented rule for a future caller that has
  no triangle (Hormann & Floater 2006, in the unit Newell plane — a third Newell implementation, because the Core cannot
  import `FaceFrame`); it is not built.

**Combination per kind.** Vector: Σ w_i·v_i per component (affine). Normalized weights (specified here, built with
skinning): sparse Σ w_i·v_i over influence keys, renormalized to 1, empty → default; negative weights (possible with MVC
in concave faces: down to −0.010 on an L-hexagon [C] [R]) are dropped before renormalizing; barycentric weights are never
negative. A weights layer accepts only `new_point = "interpolate"` (an unweighted new vertex would be unbound).

### 4.2 Point layers owned by the Mesh

**Data model** (names `PROVISIONAL`):

- `LayerId(ElementId)` in `core/ids.py`: monotonic, never reused, counter forward only (AD-001; the `ObjectId` precedent).
- `PointLayerInfo` (frozen): `name` (non-empty, unique per mesh), `kind` (`LayerKind.VECTOR`; `WEIGHTS` reserved),
  `new_point` (`"interpolate"` | `"zero"`, H2; validated per kind). No merge field: the merge rule is the average (§13 M-5);
  another rule would be an additive field.
- The mesh holds `_layer_meta: tuple[tuple[LayerId, PointLayerInfo], ...]` (order = display order) and
  `_layer_values: dict[LayerId, dict[VertexId, value]]`. Vector value: `tuple[float, float, float]`, finite; default
  `(0.0, 0.0, 0.0)`.
- The Core owns the layers and applies their per-kind arithmetic (combination, frame map, H2 rule); it does not interpret
  their **meaning** (AD-SYM-01 §3 pattern). What a layer stands for — a morph target, its weight, which view shows it —
  lives in `src/mirai`. A morph target is one vector layer; its weight stays view state (F-11). `Scene.morph_targets`
  stays reserved and `null`.

**Invariants** (contract-tested): **L1** values only for live vertices and existing layers; **L2** canonical — a value
equal to the kind's default is never stored, so layer state compares as dicts and exports deterministically; **L3** vector
values are three finite floats; **L4** names unique, `LayerId`s never reused, a layer's `kind` never changes; **L5** no
layers ⇔ `export_state()["point_layers"] is None`.

**Storage:** one sparse dict per layer, Core-internal (Phase 2–5); **packed since Phase 4** (§17: float64 arrays over one
append-only slot map per mesh, behind the same API). Measured [C] [R] (dict of tuples): one layer at 15 % / 100 %
occupancy = 0.57 / 3.96–4.09 MiB at 20k, 2.14–2.26 / 16.2–16.4 MiB at 87.5k; 50 sparse targets at 20k ≈ 29 MiB, 50 dense
≈ 200 MiB. Packed storage (an array per layer plus a slot map) is an internal change behind the same API (CORE_V1_FREEZE
§7: internals change when profiling justifies it), decided in Phase 4 against its budget (50 targets ≤ 50 MB at 20k, audit
§G); a packed float32 layer is 1 MiB at 87.5k (audit). A GPU / evaluation copy is derived, never the Core's.

**API** (`PROVISIONAL`): read `point_layer_ids()`, `point_layer_info(lid)`, `layer_value(lid, vid)` (default when absent),
`layer_items(lid)` (stored values, ascending `VertexId`); write, each journaled: `add_point_layer(info) -> LayerId`,
`remove_point_layer(lid)`, `set_point_layer_info(lid, info)` (name and rule only, never the kind),
`set_point_layer_order(ids)`, `set_layer_value(lid, vid, value)`, `map_vector_layers(m3x3)`; plus
`add_vertex(position, origin=None)`.

**Journal — two record shapes, chosen by the operation:**

- **Per element** (sparse edits: `set_layer_value`, the primitives' writes, deletion): a before-value per (layer, vertex)
  on first touch, through a `_touch_l(lid, vid)` helper like `_touch_v`. `MeshChange.layer_values:
  dict[LayerId, dict[VertexId, value | None]]` (None = absent).
- **Whole layer** (bulk: `map_vector_layers`, `remove_point_layer`, a layer replaced or dropped by `load_state`): the bulk
  operation builds a new value dict and never mutates the old one, which becomes the before-record (O(1) journal memory),
  with that recording's per-element before-records of the layer kept as an overlay (the old dict plus the overlay is the
  state at `begin_change`). Later per-element writes to that layer in the same recording need no record.
  `MeshChange.layer_whole: dict[LayerId, (old dict | None, overlay)]`.
- **Copy-on-write rule:** a value dict referenced by a record or a delta is never mutated; the first write to such a
  layer copies its dict once (O(values)). New in the revision (§13 M-2), checked by T-1 / T-2.
- **Watches record no values:** a `MeshWatch` records which layers changed and, for per-element writes, which vertices
  (keys only); before-values are held only by recordings (`begin_change`), one per nesting level (F-10). The Phase 3
  evaluation reads the keys to patch the evaluated surface.
- `MeshChange.layer_meta` (`_UNSET` or the before-meta), journaled whole like `regions`.
- `MeshDelta.layer_meta: (before, after) | None`; `MeshDelta.layer_values` per layer either per-element
  `{vid: (before, after)}` (differing entries only) or a whole `(before dict, after dict)` pair (the after dict is the live
  one, now shared under the copy-on-write rule).
- `end_change`, `rollback_change`, `revert_change`, `release_change`, `apply_delta`, `MeshChange.is_empty`,
  `MeshDelta.empty` extended. Apply order: meta that (re)creates layers, then values, then removal of layers no longer in
  the meta — L1 holds after every apply.
- `load_state` under a journal writes only differing values (whole-layer records for replaced layers); without a journal
  it also clears the old layers; it validates the whole `"point_layers"` value before its first write (an invalid file
  leaves the mesh unchanged).
- Measured, per element [C] [R]: `set_layer_value` 0.2–0.6 µs without a recording, 0.5–1.3 µs with one, 0.8–1.9 µs with
  three, 1.2–3.6 µs with five logs (two prototypes); rewriting one dense layer under one recording 11–34 ms (20k) /
  35–200 ms (87.5k); `delete_vertices(1000)` with 50 sparse layers 83 → 99 ms (20k), 133 → 146 ms (87.5k). Per-element
  journaling of a bulk rewrite on gollum with 5 dense layers peaks at 133 MiB (one recording) / 258 MiB (plus five value-
  recording watches) [R] — ≈ 1.3 / 2.5 GiB for 50 dense layers: the reason for the whole-layer record and the value-free
  watches. With them, a bulk operation journals O(layers); its history entry keeps one old dict per rewritten layer — the
  inherent cost of an exact Undo of a full rewrite, shrunk by packed storage (Phase 4).

**File** — additive keys in `Mesh.export_state()` (precedent `"symmetry"`, `"face_regions"`): a top-level
`"layer_id_counter"` beside the other counters (every content filter drops it like them, F-9) and `"point_layers"`:
`null` or `[{"id", "name", "kind", "new_point", "values": {"<vid>": [dx, dy, dz], …}}]` in display order, vertex IDs
ascending. `load_state` reads both with `.get` (old files: no layers, counter 1); an unknown kind or rule, a duplicate
name or a value for a missing vertex makes the file invalid (`ValueError`, fail-closed). JSON floats round-trip exactly
(Python `repr`). **Scene file version:** `serialization.py` writes version 5 when any mesh has point layers and 4
otherwise, and reads 2–5 — an older build then refuses a file with targets instead of silently dropping them on save
(§13 m-6); files without targets are unchanged.

**AD-023 exactness contract, point by point:** (1) counters — `layer_id_counter` only moves forward, is never in a delta,
`load_state` restores it forward; (2) journaled values — the meta like the symmetry definition, the values per element
or per whole layer; (3) record content — values are the stored float tuples, bit-exact; the meta keeps the order;
(4) iteration order — the order inside a value dict is not semantic: every reader is order-free or sorts, `export_state`
writes ascending IDs (tested order-sensitively, on the JSON text — the snapshot oracle's dict comparison is order-blind),
and the meta order is journaled; (5) rollback / abort — the same records, no snapshot; (6) "changed?" — a layer-only
change is a non-empty delta (pushes an entry, wakes the watches); new (7) — L1–L5 hold after every primitive, apply and
load.

**Consumers updated in Phase 2:** `SessionStart.unchanged()` / `.state()` include layers (F-9); `regions.inherit_into` is
unaffected; viewport, pick cache, SubD and soft-shading watches ignore layer slots (they draw the rest shape; none
misbehaves on a layer-only change [R]); a layer-only transaction notifies as a non-topology change (`moved_of → set()`,
the selection-mirror entry marked non-topology) so neither `_mesh_transaction` nor `_apply_undo_redo` rebuilds topology;
the Morph Lab's `Mesh.from_state` copies and the `morph_bridge` file carry the layers along (harmless).

### 4.3 Linear-map rule: edit vs. frame change

- **Edit** — every component tool, in object space: rest positions change, offsets do not; the target is the new rest
  plus the old offset (J-3 "relativ"; Blender's relative shape keys behave the same when the basis is edited — general
  knowledge of its design, not verified against its source). Consequences: rotating or scaling the whole mesh in
  `1`/`2`/`3` leaves the expressions in their old orientation and size (asked as a confirmation, Kurzfassung);
  Re-Symmetrize evens out the base, not the targets. The frame change is mode `4` plus Apply transform (AD-021 A-5: the
  level is always explicit).
- **Frame change** — the same shape in new coordinates: vector values map by the linear part M of the point map, weights
  stay. Apply transform: `p → to_world(p)`, M = s·R (`delta_to_world`), through `Mesh.map_vector_layers(M)` in the same
  recording as the positions, for every baked object (F-7); an identity placement maps nothing. Mirror copy: `p → H·p`,
  M = H, the new mesh's layers built through the index map. Translation never touches offsets. Exactness: after Apply,
  evaluated positions equal the old world-space evaluation up to rounding; for axis-plane mirrors (H entries 0 / ±1) the
  copy is bit-exact.
- **Cost:** `map_vector_layers` is a bulk operation (whole-layer record, §4.2): one new dict per layer, ≈ 0.4–2 µs per
  stored value [C] [R]; basemeshes (< 1k points) × 50 dense layers well under 0.1 s, gollum 87.5k × 50 dense several
  seconds [H] — the Phase 4 packed storage is the remedy if that case becomes real.

### 4.4 Operation gate (fail-closed) and Core backstop

- **Gate** (`src/mirai`, module name `PROVISIONAL` `layer_declarations.py`, beside `symmetry_declarations.py`):
  `LAYER_SAFE_OPERATIONS: Mapping[key, implementation]`, keyed as in AD-SYM-03 D-b — the resolved `C` context
  (`CContext`), command constants (removal, Collapse, Cap, Extrude, Loop Insert, Apply transform) and the menu methods
  (`MIRROR_ENTRIES`) — with a symmetric variant where the symmetric path differs (Knife, F-6). The value is the
  implementation the app already runs, so a rename fails loudly; a parametrized test runs every declared entry on a plain
  **and** a symmetric layered fixture against its rule in §3 / §4.1 — an entry without a rule fixture fails (declaration
  = tested support).
- **Key space and enumeration:** every `Application` command and method that can reach `_mesh_transaction`,
  `record_mesh_change`, `begin_change` or build a mesh from an existing one — the `commands.py` constants it dispatches,
  `MIRROR_ENTRIES`, and the public mutating methods (`mirror_copy`, `apply_mesh_change`, the scene / object methods).
  The enumeration test lists them from the code; an unclassified command **or method** fails (the AD-SYM-03 §2.5
  allow-list pattern, extended past `commands.py`).
- **Per target mesh:** the gate is consulted when a mesh the operation changes or copies has layers — the edit mesh for
  component operations, every baked object's mesh for Apply transform, the source for mirror copy — where the operation
  is resolved (after `resolve_c_context` in `_connect_command`, the G-2 position; at the Extrude / Knife arm; per command
  or method otherwise), before any mutation. It refuses visibly (status names the operation and the reason; text
  `PROVISIONAL`, e.g. `"Knife: locked while this mesh has morph targets"`). No layers: no lookup, behaviour unchanged.
- **Classes:** allowed = non-mesh commands (selection, display, modes, Undo/Redo, cancel, constraints, region / mask /
  hide / symmetry commands) ∪ position-only commands (contract test: layers bit-identical afterwards) ∪ copies that carry
  layers (Morph Lab send) ∪ declared operations.
- **Core backstop:** `add_vertex` without an origin and `split_face` with interior points but without `origins=` refuse
  on a layered mesh. The backstop catches a forgotten origin (mechanical omission); the gate catches what the Core
  cannot see — a tool that post-processes positions after a primitive (F-6), a frame change that rewrites positions
  without the map, a new mesh built from a layered one. External hosts (`apply_mesh_change`, labs) get the backstop.
- **H1 is the table's content** (§10).

### 4.5 Relation to `face_regions`

Kept as it is: membership is boolean and needs no interpolation, and the inference covers every face-creating operation
today, fail-closed. Later options, each with its trigger: (a) an exact face origin from `split_face` (the parent is known
in the primitive), when Knife interior shapes must inherit (AD-REGIONS-01 §2); (b) a face-domain layer — the same
mechanism on faces, incl. the whole-layer record — when the whole-value journal (~4 MiB / ~55 ms per change at 87k faces)
is measured too slow. Corner-domain data (UVs) would use the same primitive hook on (face, vertex) corners — not now.

## 5. Alternatives (M1 history)

| # | Alternative | Not used, because |
|---|---|---|
| X-1 | Collect origins afterwards from the journal (the regions pattern) | The journal holds the removed edge's ends but not `t`, and not a tool-built vertex's source (Extrude); recovering them is geometric inference (X-5). Every commit boundary needs a hook with its own nested-rollback bookkeeping — three region hooks already cost one broken import boundary (audit §B, fixed in Phase 0) |
| X-2 | Layers outside the Mesh (Scene, Object, an app store) | Desynchronize on Undo, Knife checkpoints and Extrude cancel unless every boundary mirrors the journal (AD-SYM-01 §1.1, AD-REGIONS-01 §1.2); need a file home of their own; contradict AD-021 §4.9 |
| X-3 | Target as a mesh copy (Morph Lab) | 52 / 207 MiB per target [C, audit]; IDs drift apart at the first topology edit (the Lab switches off); 20–50 targets do not fit 8 GB. The Lab's "beside the base" stays, as an editing view (H4) |
| X-4 | Half-Edge migration | Fixes none of the audit's four limitations (§A, §C); rewrites `mesh.py` and every tool and re-proves ~3,000 tests plus the 351-test Knife oracle; AD-002 keeps the swap possible later |
| X-5 | Geometric inference (midpoint matching, nearest point) | Medium reliability (FINDINGS-3AB), fails for t ≠ 0.5 (AD-017 B1b), ambiguous for coincident midpoints. Stays the tool for transfer between *different* meshes (Phase 7) |
| X-6 | AD-005 listener design (`topology_listeners`, `on_vertex_created(new, parent, context)`) | One parent is wrong for an edge split (a blend); listener-held data lives outside the journal, so `rollback_change` / `revert_change` (Knife checkpoints, nested Collapse) would not restore it; bones on the Mesh contradict AD-021 §4.9; never implemented, superseded |
| X-7 | A stored provenance record (origin per vertex in the Mesh, the journal or History) for later remapping | No consumer needs it once layers get their values at mutation time; it grows with every edit; ARCH-02: no large remapping framework before real use cases |
| X-8 | Whole-value journaling of layers for every change (like `face_regions`) | A dense 87.5k layer is 16 MiB per change for a one-point edit; regions already measure ~4 MiB / ~55 ms per change at 87k faces. Kept only for bulk operations (whole-layer record) |
| X-9 | Absolute target storage (a position per point and target) | Every base edit would have to update every target (J-3 asks for the opposite); a new point's interpolated absolute position would not match its exact rest position — offsets keep the rest point where the artist cut |
| X-10 | MVC per `split_face` call in the Core (the first draft) | The value of a closed Knife shape would depend on the resolver's decomposition and bridge rule (2.4–30 % of the spread [R]); an MVC point can leave the target's drawn surface (up to 75 % of the offset [R]). The Knife already knows its triangle: barycentric weights over the original corners are passed in, and the Core needs no triangulation (§4.1) |
| X-11 | All interpolation in the Core in Phase 2 (the first draft) | CORE_V1_FREEZE §1 ("nicht vorsorglich"): in Phases 2–4 the Knife interior rule has no caller (H1 locks the Knife; ANIMATION.md item 5 allows the lock) and its rule was not settled. Phase 2 keeps only rules that are the position's own arithmetic |
| X-12 | Gate only, no Core backstop | A tool calling `add_vertex` without an origin would silently store zero offsets (dents) — against the "never silently wrong" intent of ANIMATION.md item 5 |
| X-13 | Core backstop only, no gate | Cannot see semantic misuse (F-6, frame changes, copies) |
| X-14 | Layer values inside the vertex record (`_VertexData` / `VertexRecord` carries them, so `_touch_v`, `_apply_records`, deletion and load handle layers for free) | `VertexRecord` is read as a position (`knife_resolve.py:309`, `SessionStart.state()`); every position write would copy a larger record; one layer write would journal all layers of the vertex; a bulk rewrite could not use a whole-layer record |
| X-15 | Merge rule "keep one point's value" (audit H3 alternative) | Which point survives depends on edge orientation and ID order, nothing the artist sees; under symmetric Collapse 6 of 6 test collapses kept a mirror-side survivor that is not the partner of the source-side one [R] — the target turns asymmetric. A defined alternative can be added when asked (§10) |
| X-16 | Per-element journaling for bulk operations, values in every watch (the first draft) | ≈ 1.3 GiB (one recording) / 2.5 GiB (plus five watches) for Apply transform on gollum with 50 dense layers [R]; no watch reads old layer values |

## 6. Artist-facing consequences

- Nothing visible changes before Phase 3; Phase 2 is Core plus tests.
- With targets, the base's picking, selection and the tools stay on the rest shape (F-11 "hilft").
- An expression follows later base edits (J-3); a whole-mesh rotate / scale in `1`/`2`/`3` is an edit, and Re-Symmetrize
  evens out the base only (§4.3). The first point is asked as a one-line confirmation (Kurzfassung).

## 7. Phasing (refines audit §G)

- **Phase 2 — Core layers and gate.** In the Core: layers, journal (both record shapes, copy-on-write, value-free
  watches), file (additive keys, version 5 with layers), deletion, `add_vertex(origin=…)` with the backstop, the exact
  rules (`split_edge`, `collapse_edge`, `collapse_elements` average), `split_face` refusing interior points on a layered
  mesh, `map_vector_layers`. In `src/mirai`: the gate with the H1 default table and its enumeration, the F-9 / §4.2
  consumers. No UI and no target creation in the app; exercised by tests. Needs the review disposition (done, §13) and
  Manu's go for the Core change (given 2026-10-27), **not** the H answers.
- **Phase 3 — one persistent target** (audit Phase 3; **built 2026-10-27, §15**). Needs H1 (the table as shipped) and H4. Includes the Apply
  transform wiring (one `map_vector_layers` call per baked object, F-7) — decided here, so `Strg+A` works with targets from
  the first app version. The editing view needs its own Undo command that writes layer values (a gesture on the view is no
  position write; F-8).
- **Phase 4** — multiple targets (audit Phase 4); the packed-storage decision belongs here (**built 2026-10-27, §17**).
- **Phase 5 — topology edits with targets** (**built 2026-10-27, §16**), one operation at a time with its acceptance test and gate lift: Split /
  Edge Connect / Loop Insert (only the gate entry — the edge blend exists), Collapse (gate entry), Extrude (`origin=`),
  the Knife (`split_face(origins=…)` as the second small Core change, origins from the hit triangle, the symmetric replay
  at the mapped t), mirror copy (layer copy through the index map); the artist test (loops around eyes and mouth with 3
  targets). H2 / H3 become visible here.
- **Phases 6–7** unchanged; the weights kind is built with Phase 6.

## 8. CORE_V1_FREEZE §7 for the Phase 2 Core extension

1. **Requirement.** Persistent morph targets (ANIMATION.md items 1–3; 20–50 targets, AD-023 header) need per-point data
   that rides Undo, Knife checkpoints, rollback and the file. Topology edits after targets are a planned strength
   (ANIMATION.md item 5, Manu 2026-10-20) that may stay locked now but must not be blocked: every operation reachable on a
   layered mesh needs a defined value for the points it creates or merges, or a refusal.
2. **Public API?** No: data outside the mesh desynchronizes (X-2); the journal cannot reconstruct origins (X-1, X-5);
   whole-value data on the mesh is too expensive at this size (X-8).
3. **Architecture problem documented:** this AD and the audit.
4. **Smallest extension:** `core/ids.py` — `LayerId`. `core/mesh.py` — `LayerKind`, `PointLayerInfo`, layer storage,
   `_touch_l`, the `MeshChange` / `MeshDelta` layer slots (both record shapes; the watch flag), copy-on-write, the layer
   methods of §4.2, the origin in `add_vertex` (keyword with a default), the rules in `split_edge` and `collapse_edge`,
   the interior-point refusal in `split_face`, value deletion in `_delete_vertex`, the `export_state` / `load_state` keys,
   the apply order. `core/operations/collapse.py` — the group average. `core/serialization.py` — version 5 when layers
   exist. `core/__init__` — exports. **Not touched:** `Operation`, `OperationContext`, `HistoryStack`, `MeshDeltaCommand`
   (it carries the delta unchanged), `MeshStateCommand`, `Scene`, `Selection`, every existing signature. **Without layers
   the behaviour is byte-identical**; `export_state` gains two additive keys.
5. **Contract tests:** §9.
6. **Then implement**; record the §7.1 entry and update CORE_V1_FREEZE §4 ("Morph Targets": storage in the Core;
   "Herkunfts-/Provenance-Metadaten": origins are applied, not stored) in the same commit. Phase 5's `split_face(origins=…)`
   is its own small §7 entry.

## 9. Phase 2 contract tests and acceptance

| # | Test | Guards |
|---|---|---|
| T-1 | Randomized journal sequences with layers (extends `tests/test_mesh_change_journal.py`): a grid with three layers (two sparse vector layers, one with the `zero` rule), `_random_op` over every primitive plus `add_vertex(origin)` and the layer writes (add / remove / rename / reorder, set incl. the default, `map_vector_layers`, sparse edits after a bulk write in the same and in a later recording); L1–L5 after every step; Undo to the start and Redo to the end against the snapshot oracle (export incl. `"point_layers"`, container orders, every counter forward incl. `layer_id_counter`); the existing 12 seeds × 25 steps plus one long run | exactness contract (1)–(7), copy-on-write |
| T-2 | Nested rollback, `revert_change`, `release_change` with both record shapes (the Knife checkpoint pattern); a watch sees layer-only changes as keys and holds no values; a layer-only change is a non-empty delta | (5), (6), §4.2 watches |
| T-3 | Rule per primitive: `split_edge` values bit-equal to the position expression; `collapse_edge` and `collapse_elements` average (group mean of original values); `add_vertex` origin copy bit-exact, weighted origin, `()` → defaults, `None` with layers → `MeshError` with mesh and counters unchanged; `split_face` k > 0 with layers → `MeshError` before the first mutation, k = 0 unaffected; `new_point="zero"`; Delete / Dissolve remove values; weights-kind rule validation | §4.1 |
| T-4 | No-layer equivalence: every existing suite unchanged; layer-free random sequences export identically apart from the two additive keys; files without layers stay version 4 | byte-identical behaviour |
| T-5 | File: export → JSON → load bit-exact (values, ids, names, order, rule, counter), order-sensitive on the JSON text; a file without the keys loads; invalid kind / rule / duplicate name / dead vertex → `ValueError` with the mesh unchanged; a non-journal `load_state` drops stale layers; `load_state` under a journal records only differing values; version 5 written exactly when layers exist, versions 2–5 read | §4.2 File |
| T-6 | `experiments/knife_oracle/tests` green (trigger list: `split_face`, `split_edge`, the journal; no layers there). The layered Knife test — each interior value equals the barycentric rule over the original face's corners, independent of the bridge choice; Undo exact — belongs to Phase 5 | §4.1 Phase 5 |
| T-7 | Gate: the enumeration test over commands **and** methods; an undeclared operation on a layered target mesh is refused before any mutation (mesh, history, selection unchanged, status set) — incl. Apply transform with one layered object among several and mirror copy of a layered source; the H1 defaults run; position-only commands keep layers bit-identical; without layers no lookup (existing app tests unchanged) | §4.4 |
| T-8 | `map_vector_layers` on random matrices (whole-layer record, identity records nothing) | §4.3 |
| T-9 | `SessionStart.unchanged()` / `.state()` with layer changes; a layer-only transaction and its Undo rebuild no topology | F-9, §4.2 consumers |
| T-10 | Mutation checks by hand, as in AD-023 §9: a write path without `_touch_l`, a bulk operation that mutates the old dict, a write to a shared dict without the copy, a wrong apply order, no value deletion in `_delete_vertex`, `split_edge` with swapped weights, an unsorted export, a non-journal load that keeps stale layers — each must fail a test | the tests themselves |

**Measured and recorded** [C], gollum_20k and gollum (87.5k): memory per layer at 15 % / 100 %; `set_layer_value` with one
and five logs; `split_edge`, `collapse_edge`, `delete_vertices(1000)` with 0 / 10 / 50 layers; one dense layer rewrite;
`export_state` + `load_state` with 50 sparse layers; **Apply transform with 50 sparse and 10 dense layers at 87.5k, peak
memory with five watches**. **Acceptance:** within 1.5× of this AD's numbers (§4) or explained; the bulk case's journal
memory O(layers), not O(values). No reference-PC run is needed for Phase 2 (no UI).
**Runs** (AGENTS.md §8a, `src/core` change): `pytest tests -q`; GL tests in their own process; `experiments/morph_lab/tests`;
`experiments/knife_oracle/tests`. **Done:** all green, the CORE_V1_FREEZE §7.1 entry and §4 update, an implementation note
here with the measured numbers, status → IMPLEMENTED (Phase 2).

## 10. Artist decisions H1–H5 as parameters

**Decided (Manu, 2026-10-27): "ja" to H1–H5 and C-1** — the defaults below are the decisions.

| | Decides | Lives in | `PROVISIONAL` default | Needed by |
|---|---|---|---|---|
| H1 | Which operations run while a mesh has targets | the gate table's entries (§4.4) | allowed: Delete, Dissolve, Vertex Connect, Cap, every position-only tool, Apply transform (from Phase 3); locked with a message: Split, Edge Connect, Loop Insert, Knife, Extrude, Collapse, mirror copy — lifted one by one in Phase 5 (all lifted 2026-10-27, §16) | Phase 3 |
| H2 | What a new point does in an existing target | `PointLayerInfo.new_point` | `"interpolate"` (follows its neighbours linearly; a touch-up may be needed in strongly bent areas) | Phase 5 (visible) |
| H3 | What merged points keep | the merge rule (average; an alternative would be an additive per-layer field) | average (matches the merge-at-centre position) | Phase 5 (visible) |
| H4 | How a target is edited | the Phase 3 editing view; no Core impact (both answers write the same layer values) | beside the base (J-5), shape edits on the view, topology only on the base | Phase 3 |
| H5a | Order: topology-after-morphs before skinning | the phase plan | yes (Phase 5 before Phase 6) | Phase 5 |
| H5b | Morph + SubD shown together | the phase plan | from Phase 4 (multiple targets) | Phase 4 |
| H5c | Speed target until the GPU phase | Phase 3 / 4 acceptance | fluid on head and body; "usable, not fluid" on gollum_20k | Phase 3 |
| C-1 | Confirmation: whole-mesh rotate / scale in `1`/`2`/`3` leaves the target movements as they were | §4.3 edit rule | yes (J-3, Blender-like) | Phase 3 |

## 11. Deliberately not decided

- **Skinning data model:** influence keys, maximum influences, normalization tolerance, bind pose, where bindings live
  beyond AD-021 §4.9 — and therefore the final shape of the weights kind.
- ~~**Evaluation location and chain**~~ — decided with Phase 4 (§17.1): CPU (`morph_mix`), the stage chain above H7,
  SubD on the mixed cage, normals from the evaluated mesh. Still open: a GPU path (its trigger in §17.1).
- ~~**Multi-target evaluation rules**~~ — decided with Phase 4 (§17.1): additive, 0–100 %, no clamping or normalization,
  drift guard by construction. Still open: correctives / combination shapes, weights beyond 0–100 %.
- **Transfer between different meshes:** retopology, import, linking a mirror copy's targets to its source's, morph
  export (OBJ / glTF).
- ~~**Editing-view mechanics**~~ — decided with Phase 3 (§15). Still open: editing on a deformed pose; symmetric target
  editing beyond what the app's symmetric tools already do on the view (they mirror positions, so offsets come out mirrored).
- **Weights as document state / animation** (`Scene.morph_targets` stays reserved, `null`).
- A merge rule other than the average (H3 alternative); face- and corner-domain layers. (Packed storage: built, §17.)

## 12. Risks and their guards

| Risk | Guard |
|---|---|
| A write path misses `_touch_l`, or a bulk operation mutates a shared dict → Undo leaves a stale value | T-1 oracle, T-2, T-10 mutation checks |
| A tool adds vertices without origin | Core backstop (raises), T-3 |
| A tool post-processes positions after a primitive (F-6) | gate entry only with its rule test on plain and symmetric fixtures (T-7), Phase 5 fix |
| An entry point outside `commands.py` changes or copies a layered mesh | enumeration over commands and methods, per target mesh (T-7) |
| History keeps large layer copies after bulk operations | whole-layer record (one old dict per layer, §4.2); packed storage in Phase 4 |
| An older build drops targets on save | version 5 with layers (§4.2 File) |
| File grows with dense targets | sparse canonical storage (L2); packed storage in Phase 4 |
| Readers of `MeshChange` internals miss layers | T-9; grep for `MeshChange` slot readers in Phase 2 |

## 13. Review CLAUDE-001 and disposition

The independent first-pass review is archived unedited:
[AD-025_REVIEW_CLAUDE_001](../archive/deformation/reviews/AD-025_REVIEW_CLAUDE_001.md) (fresh session, review only, at
`83044a2`). Verdict **ACCEPT WITH CHANGES**, no blocker. Disposition:

| Finding | Disposition |
|---|---|
| M-1 Closed-Knife composition error understated; tool-supplied origin not considered | **Accepted.** Numbers corrected (§4.1). `split_face(…, origins=…)` added as the Knife path (Phase 5); the Knife passes barycentric weights of its hit triangle over the original face's corners; MVC only as the documented, unbuilt fallback; X-10 rewritten; T-6 compares with the direct rule |
| M-2 Bulk layer operations journaled per element cost GiB; watches multiply it | **Accepted, in Phase 2.** Whole-layer record for bulk operations, value-free watches (§4.2); a measured row for Apply transform with five watches (§9). The copy-on-write rule that makes the shared dicts safe is the author's addition, not reviewed; T-1 / T-2 / T-10 test it |
| M-3 Fail-closed enumeration covers `commands.py` only; Apply transform acts on every baked mesh | **Accepted.** Key space = commands and methods incl. `MIRROR_ENTRIES`; check per target mesh (§4.4, T-7) |
| M-4 Phase 2 builds interpolation ahead of any consumer | **Accepted (first option).** Phase 2 keeps the exact rules; `split_face` interior points refuse on a layered mesh until Phase 5; CORE_V1_FREEZE §4 updated in the implementing commit (§7, §8, X-11) |
| M-5 H3 `"keep"` ill-defined and not mirror-consistent | **Accepted.** `"keep"` dropped, no merge field; H3 = average, an alternative is specified when asked (§10, X-15) |
| m-1 MVC metric ill-conditioned | Accepted: stable metric quoted (§4.1) |
| m-2 Viewport projects onto the dominant axis plane | Accepted: F-5 corrected; the third Newell implementation noted with the unbuilt MVC fallback |
| m-3 Transforms commit position snapshots, not recordings | Accepted: F-8 corrected; editing-view command noted under Phase 3 (§7) |
| m-4 More logs than "up to six" | Accepted: F-10 states the real bound (watches + one recording per nesting level); watches no longer hold values |
| m-5 Kurzfassung's Ctrl+A promise vs. the H1 default | Accepted: Apply transform wiring decided for Phase 3; Kurzfassung and H1 agree |
| m-6 Older builds drop `"point_layers"` silently | Accepted: scene file version 5 when layers exist (§4.2) |
| m-7 Three missing mutation checks | Accepted: order-sensitive export, stale layers after a non-journal load, kind immutable and load validated first (§4.2, T-5, T-10) |
| m-8 Layer-only changes take the topology path | Accepted: non-topology notification (§4.2 consumers, T-9) |
| m-9 Missing alternative; one silent artist decision | Accepted: X-14; the whole-mesh rotate / scale rule asked as confirmation C-1 |
| n-1 Morph Lab copies carry layers | Accepted: §3 row, §4.2 consumers |
| n-2 Re-Symmetrize leaves targets asymmetric | Accepted: §3, §4.3, §6 |
| n-3 H5 bundles three questions | Accepted: H5a / H5b / H5c |
| n-4 Identity placement should record nothing | Accepted: §3, §4.3, T-8 |
| n-5 T-4's export-key exception is empty | Accepted: clause dropped |
| n-6 "Does not interpret them" | Accepted: "does not interpret their meaning" (§4.2) |

No second review is planned: the revision takes the review's own proposals; the one addition (copy-on-write) is an
implementation-level rule that Phase 2's oracle tests decide. If Manu wants a check of the revision, a short re-review of
§4.1, §4.2 and §4.4 is enough.

## 14. Implementation note (Phase 2, 2026-10-27)

**Built** (CORE_V1_FREEZE §7.1 entry of the same date): `LayerId`, `LayerKind`, `PointLayerInfo` and the §4.2 API in
`core/mesh.py` (plus `has_point_layers()`); `add_vertex(position, origin=None)`; the exact rules in `split_edge`,
`collapse_edge`, `collapse_elements`; the `split_face` interior-point refusal; value deletion in `_delete_vertex`; both
journal record shapes with copy-on-write and value-free watches; `"layer_id_counter"` / `"point_layers"` in the export and
scene file version 5 with layers; `map_vector_layers`. App side: the gate `src/mirai/layer_declarations.py` (H1 default
table), checked in `key_press`, `dispatch_command`, after `resolve_c_context`, per baked object in Apply transform and for
the source of mirror copy; `SessionStart.unchanged()` / `.state()` read the layers; a layer-only `_mesh_transaction` is a
non-topology step (no topology rebuild, its mirror entry `mesh_step=False`).

**Implementation choices within the decision** (names `PROVISIONAL`):

- `MeshDelta` carries the two shapes in two fields, `layer_values` (`{lid: {vid: (before, after)}}`) and `layer_whole`
  (`{lid: (before dict, after dict)}`), instead of one mixed dict; `MeshChange` has `layer_meta`, `layer_values`,
  `layer_whole` and `keys_only` (a watch). Layer existence rides the whole-layer record (`add_point_layer` /
  `remove_point_layer` write `None ↔ dict` whole), so per layer a recording or delta holds per-element records **or** one
  whole record, never both (pinned in T-1). Consequence: the §4.2 apply order cannot change the result; the T-10 mutation
  "wrong apply order" survives by construction, the mutation that breaks the disjointness is caught.
- §4.1 "a new or merged vertex … unless `new_point` is `zero`": read as **H2 applies to new points only**; a merge averages
  in every layer (H3, the position's arithmetic). A merged survivor losing its offset in a `zero` layer would be a dent,
  which H2 does not ask for.
- `LayerKind.WEIGHTS` exists for the rule validation (`PointLayerInfo` refuses `new_point="zero"` for it); `add_point_layer`
  and the file refuse the kind until Phase 6 builds its values.
- `load_state` under a journal: whole-layer records for layers that appear or go, per-element records for the differing
  values of a layer that stays.
- Gate key space beyond the §4.4 list: `CContext.NONE` is non-mesh; `SPLIT_EDGE`, `KNIFE_COMMIT`, `KNIFE_LIFT`,
  `ARTICULATION_RESTORE` are locked (no `Application` path changes a mesh with them outside a locked Knife session;
  fail-closed). Apply transform is skipped at dispatch (`PER_TARGET_COMMANDS`) and checked with every baked mesh.

**Measured [C]** (container, Python 3.13; scratchpad probes against the real `Mesh`, not kept; gollum_20k = 21,875 V,
gollum = 87,500 V; container timings vary up to ~2× between runs):

| Quantity | gollum_20k | gollum (87.5k) | AD (§4.1–§4.3) | Verdict |
|---|---|---|---|---|
| memory one layer 15 % / 100 % | 0.57 / 4.09 MiB | 2.27 / 16.35 MiB | 0.57 / 3.96–4.09; 2.14–2.26 / 16.2–16.4 | equal |
| `set_layer_value`, no recording | 0.86 µs | 1.04 µs | 0.2–0.6 µs | **1.7×, explained:** the AD's prototypes wrote raw dict entries; the real path validates L3 (three finite floats) and the canonical form L2 |
| `set_layer_value`, 1 / 3 recordings | 1.16 / 1.57 µs | 1.40 / 2.90 µs | 0.5–1.3 / 0.8–1.9 µs | within 1.5× |
| `set_layer_value`, 1 recording + 4 watches | 1.99 µs | 2.02 µs | 1.2–3.6 µs (5 logs) | within |
| `split_edge`, 0 / 10 / 50 sparse layers (one recording) | 0.029 / 0.032 / 0.072 ms | 0.026 / 0.061 / 0.111 ms | 0.024–0.028; +0.01; +0.04–0.06 | within 1.5× (the 87.5k 10-layer row 1.6× in one run, 20k 0.9×: run noise) |
| `collapse_edge`, 0 / 10 / 50 layers | 0.036 / 0.045 / 0.133 ms | 0.037 / 0.055 / 0.175 ms | — | recorded |
| `delete_vertices(1000)`, 0 / 10 / 50 layers | 89 / 100 / 106 ms | 110 / 108 / 132 ms | 83 → 99; 133 → 146 ms | within |
| one dense layer rewritten per element, one recording | 21–66 ms | 87 ms | 11–34 / 35–200 ms | within (run-to-run spread) |
| one dense layer, `map_vector_layers` | 15–27 ms | 61 ms | — | the bulk path is cheaper |
| export / load, 50 sparse layers (fresh process) | 123 ms / +141 ms over 693 ms | 483 ms / +2.3 s over 3.35 s | — | recorded (load ≈ 0.9 / 3.5 µs per value; the large heap's GC dominates at 87.5k) |
| Apply-transform case: `map_vector_layers`, 50 sparse + 10 dense layers, 1 recording + 5 watches | 0.83 s (382,800 values) | 3.26 s (1,531,250 values) | 0.4–2 µs per value; "several seconds" [H] | 2.2 µs per value: within 1.5× |
| … traced memory of that bulk write | 69.6 MiB | 279 MiB peak, 277 MiB kept | per-element journaling: 1.3 / 2.5 GiB for 50 dense [R] | the peak is the 60 new value dicts themselves; **journal O(layers): 60 whole-layer records, 0 per-element records, watches 60 layer keys and 0 vertex keys** |
| Undo / Redo of that bulk write | < 0.1 ms | < 0.1 ms | — | dict swaps (one probe run showed 70–245 ms: a GC pass after the large allocation, not the apply) |

**Tests:** `tests/test_point_layers.py` (T-3, T-4, T-5, T-8), `tests/test_mesh_change_journal.py` (T-1: 12 seeds × 25 steps
plus one 300-step run over every primitive and layer write, L1–L5 after each step, Undo / Redo against the snapshot oracle
and the JSON text; T-2: nested rollback, checkpoints with revert / release, watches, copy-on-write), `tests/test_layer_gate.py`
(T-7: enumeration of commands, contexts and methods incl. `MIRROR_ENTRIES` from the code; every declared entry on a plain
and a symmetric layered fixture; locked operations refused untouched and running without layers; Apply transform per
baked object; mirror copy; position-only commands keep layers bit-identical; no lookup without layers; T-9). **T-10 by
hand:** caught — a write without `_touch_l`, a bulk operation mutating the old dict, a write to a shared dict without the
copy, no value deletion in `_delete_vertex`, `split_edge` with swapped weights, an unsorted export, a non-journal load
keeping stale layers, and a bulk write leaving per-element records beside its whole record; survives by construction —
the apply order (see above).

**Open after Phase 2:** Phase 3 — built, §15.

## 15. Editing view and Phase 3 implementation note (2026-10-27)

### 15.1 Decision: the editing view (H4 mechanics, §11) — agent decision, names `PROVISIONAL`

Requirements taken from the Morph Lab (J-5 "daneben" KEEP, J-3 "relativ", F-11 weight = view, 6a picking on the rest shape
"hilft", the Lab's own limits) and from §4.2 / F-8; the Lab's file structure is not copied (M3).

1. **The view is a transient scene object.** `Tab` on a base with a target adds an object whose mesh is an ID-identical copy
   of the base at `b + d` (no layers; `morph_targets.view_state`), placed 1.25 world widths of the base along +X with the
   base's rotation, scale, pivot and material, and makes it the edit object (E-14 `_set_edit_object`). Every app tool runs on
   it unchanged; the component selection carries over (same IDs); the camera pans by the same offset (the shape stays where it
   was on screen; zoom out to see the base beside it). Opening and closing are no Undo step. The view lives while it is the
   edit object: `Tab` again, an Undo that brings back another edit object (Q-8), or a scene load closes it. It is never a
   document: `save_scene_file` writes the scene without it (base = edit object), OBJ export and the `M` bridge take the base.
2. **A gesture on the view is one offset write (F-8).** The app's history is `morph_targets.TranslatingHistory`, a subclass of
   the Core `HistoryStack` in `src/mirai` (Core unchanged): while a view is open every push goes through `TargetView.translate`
   — the view's `Mesh.watch()` (keys only) names the touched points, their offsets `p − b` are written into the base's layer in
   **one** `record_mesh_change`, and that `MeshDeltaCommand` on the base replaces the view's own command; the view is then
   re-derived as `b + d` on those points (bit-exact by definition). Only touched points are written, and the delta holds only
   the ones that changed. One choke point covers every tool (W/E/R, Tweak, Soft, Smooth, Relax, Loop Slide, Re-Symmetrize, the
   host `apply_mesh_change`) instead of a hook per gesture path. A push that keeps nothing sets `swallowed`, and the selection
   mirror skips its entry (the stacks stay 1:1). Undo / Redo change the base's layer; `TargetView.sync_from_base` brings the
   view back to `b + d` (or rebuilds it if an older step changed the topology).
3. **Topology only on the base.** A second gate table for the view (`layer_declarations.view_refusal`): non-mesh and
   position-only commands and the morph keys run; every topology operation (also the H1-allowed Delete, Dissolve, Vertex
   Connect, Cap), Apply transform, `Shift+S`, saved-region edits, mode `4` and adding objects are refused with
   `"<operation>: on the base only (Tab returns to it)"`. Fail-closed backstop: `translate` reverts a view change that is not a
   position change (a host bypassing the keys) and keeps nothing.
4. **Weight = view state** (F-11): per object in whole percent, no Undo step, not saved; keys `+`/`-` (10 %), `Shift` (1 %),
   `Alt` (100 % / 0 %), and hold `N` + mouse left/right (Manu's J-4 "Schieberegler" without window UI; tap `N` = 0 % ↔ last).
   Display through H7: `morph_targets.MorphSurfaceProvider` shows `b + w·d` as the edit object's surface and, H7-E, on the
   base beside the view. **The wire follows the mix** (Manu 2026-10-27, after the first try: "das Wireframe geht nicht
   mit, nur die Polygone"; viewport hook `provider.wire_follows_surface`, additive to H7); selection, hover, picking and the
   tools stay on the rest shape (Morph Lab 6a "hilft" — `PROVISIONAL` reading: his note is about the wire only). Cost [C]:
   with the wire shown a weight step rebuilds it (gollum_20k, 43,750 edges: +22 ms; head / body < 1 ms). The H7 slot is shared with the SubD preview: whoever
   holds it keeps it, the other says so (H5b: together from Phase 4). The surface patches from the base's journal: a weight step
   touches only the points with an offset (`_Surface`, `(b, d)` cached), an edit only the touched ones; since Phase 5 a
   topology edit on the base is patched in as well instead of rebuilding the surface (§16.1).

Alternatives considered: in-place editing with a target switch (Blender-style; Manu chose "daneben", H4); a persistent second
object as in the Lab (X-3: desync and memory); every tool writing offsets itself (touches every tool, many paths to keep in
step); a commit hook per gesture path (six paths, a seventh would be missed silently — the push is the one boundary they share).

### 15.2 What was built

- `src/mirai/morph_targets.py` (new): names (`Target n`, rename cycle), `MAX_TARGETS = 1`, keys (context `"morph"`, resolved
  after global and SubD; none collides with an app or Morph Lab key), `TranslatingHistory`, `TargetView`, the provider and its
  slot (`MorphDisplay`). `Application`: `create_morph_target` / `rename_morph_target` / `delete_morph_target` (`Ctrl+N`,
  `Ctrl+Shift+N`, `Alt+Shift+N`; one layer-only `_mesh_transaction` each, base only), `edit_morph_target` /
  `leave_morph_target` (`Tab`), `set_morph_weight`, the hold-`N` drag, `morph_document_object`, `_document_scene`; HUD row
  "Morph" (only with a target).
- **Apply transform** (F-7): `scene_objects.apply_placement` calls `Mesh.map_vector_layers(s·R)` after the positions, inside
  the same `record_mesh_change` per baked object; identity records nothing. `layer_declarations`: `APPLY_TRANSFORM` declared
  (`apply_placement` for plain and symmetric), the lock lifted.
- **Morph Lab and `M`** (decision, `PROVISIONAL`): both stay. The Lab is the Discovery tool for what Production does not do
  (jaw pose, relative ↔ absolute, the HUD timing); `M` still sends a copy. A mesh with a Production target arrives as the Lab's
  pair — base = rest shape, "Ziel 1" = rest + the first target's offsets, both without layers (`lab_scene.build_pair_scene`);
  nothing comes back. During target editing `M` sends the base.
- Unchanged: the Core, the H1 table on the base (Phase 2 rules: Delete / Dissolve keep the survivors' offsets exactly).

### 15.3 Measured [C] (container, Python 3.13, Mesa llvmpipe; `xvfb-run -a python experiments/drag_cost/probe_morph_gl.py`)

| Row | head_basemesh (326 V) | Man_With_Shoes (928 V) | gollum_20k (21,875 V) |
|---|---|---|---|
| weight step p50 / p95, offsets on 15 % | 0.84 / 1.20 ms | 1.30 / 1.80 ms | 34 / 52 ms |
| weight step p50 / p95, offsets on 100 % | 2.54 / 4.94 ms | 7.25 / 10.4 ms | 203 / 255 ms |
| first show (0 → 1 %, builds the surface) | 11 ms | 29–63 ms | 1.3–2.7 s |
| tap `N` 0 % → 60 % (surface kept, GL buffers rebuilt) | 7.5 ms | 21 ms | 0.7–0.9 s |
| view gesture commit (36 points, the release) | 3.1 ms | 4.0 ms | 30 ms |
| Apply transform with one target | 1.8 ms | 3.8 ms | 81 ms |

A weight step = the hold-`N` mouse move + `update_viewport` (provider + `Viewport.sync`), without the draw. **Verdict:** head
and body are far under the 16.7 ms bar in the container; the reference PC runs Python ≈ 2× slower (REFERENCE_HARDWARE §2),
which keeps head comfortable and the dense body row near 10–20 ms — **only the reference PC can confirm the bar** (run the
probe there). gollum_20k is "usable, not fluid" (H5c) with sparse targets (≈ 35–50 ms) and slow with a dense one (≈ 0.2 s per
step): the cost is the viewport's incremental patch of every moved vertex (normals and face rows, `render_mesh._sync_geometry`),
not the evaluation (profiled: provider ≈ ¼) — the shared bottleneck of any whole-mesh move, for the Phase 4 GPU evaluation
probe. Tab into the view on gollum_20k pays one mesh copy (≈ 1 s).

**Tests:** `tests/test_morph_targets.py` (lifecycle with exact Undo / Redo; one target per mesh; save → load bit-exact, also
with the view open; the view equals `b + d`; W/E/R/Tweak/Soft/Smooth on the view = one Undo step on the base writing only the
touched offsets; 13 topology and base-only commands refused on the view untouched; the backstop; Undo across the session; Delete
/ Dissolve on the base keep the survivors' offsets; C-1; the weight is no history entry and not saved; the drag; the mix on
the base and beside the view; the SubD slot; the HUD row; a randomized oracle of the evaluated surface; the bridge),
`tests/test_layer_gate.py` (Apply transform plain and symmetric, one layered object among several, world shape equal to 1e-12,
mirror-exact offsets after a 90° bake, identity maps nothing, Undo / Redo), `experiments/morph_lab/tests/test_app_lab.py`
(a sent Production target becomes the Lab's pair), `experiments/drag_cost/tests/test_probe_morph_args.py`.

**Next (H5a):** Phase 5 (topology edits with targets, one gate lift at a time) before skinning — built, §16; Phase 4 (several targets,
packed storage, stage chain, GPU evaluation) is independent of it. Open from Phase 3: the reference-PC run of the probe; mask
and hide sets are not carried onto the view; Manu's practical test (Kurzfassung).

## 16. Phase 5 implementation note (2026-10-27)

### 16.1 What was built

- **Core (CORE_V1_FREEZE §7.1 entry of the same date):** `Mesh.split_face(…, origins=None)` — one `VertexOrigin` per
  interior position; required for k ≥ 1 on a layered mesh, validated and combined before the first mutation (the
  `add_vertex` arithmetic, `_origin_values`), written through the journaled per-element path. Nothing else in the Core.
- **Knife origin at the pick:** `picking.face_hit` returns the hit position (bit-identical to `face_hit_position`, now its
  wrapper) and the barycentric weights of the hit triangle over its corners (`triangle_origin`); `knife_pick` adds them
  to a face target as `"origin"` when the mesh has layers. `KnifeTool` stores the origin in the face record; a target
  without one (a host, a headless session) gets the same rule from the face's triangulation (`face_point_origin`: the
  triangle that holds the point). The record travels to the camera-free resolver.
- **Resolver:** `RecordedMesh.origins` (only on a layered mesh) maps each interior position to its origin — filled from
  the face records, and for a point the run makes where it crosses itself, with the blend of its two segment ends at the
  crossing parameter (`blend_origins`; affine like every Knife value). `kept_split_face` passes the origins; a position
  without one passes none, so Core refuses and the run is dropped (fail-closed). `KeptSplitFace.origins` records them.
- **Symmetric Knife (F-6):** the mirror `split_edge` runs at the mapped t (`t`, or `1 − t` when the mirror edge is stored
  the other way round), then the position is snapped as before; the mirror `split_face` gets the source origins through
  the vertex map.
- **Extrude:** every cap vertex is `add_vertex(position, origin=((v, 1.0),))` — the drag moves positions only.
- **Mirror copy:** `object_mirror.mirror_mesh` copies every layer in order (name, rule) through the index map, values
  `v → H·v` with the position's arithmetic (bit-exact for the axis planes).
- **Gate:** `LAYER_SAFE_OPERATIONS` declares Split (`Mesh.split_edge` / `coordinate_split`), Edge Connect and Loop Insert
  (`apply_connect_edges` / `coordinate_edge_connect`), the Knife (`resolve_cross_face` / `coordinate_knife`), Collapse
  (`apply_collapse` / `coordinate_collapse`), Extrude (`ExtrudeTool` / `plan_extrude`) and mirror copy (`mirror_mesh`);
  every H1 lock is lifted. Still locked: `SPLIT_EDGE`, `ARTICULATION_RESTORE` (no `Application` path handles them). The
  Knife session keys (`KNIFE_COMMIT`, `KNIFE_LIFT`) are non-mesh outside a session; the session is gated at `C`.
- **The mix follows a topology edit in place** (found by the Phase 5 probe, §16.3): the Phase 3 surface rebuilt itself
  from scratch on every topology change of the base — `export_state` + `Mesh.from_state` + a new `RenderMesh`, ≈ 3–4 s
  on gollum_20k with a target dialled in, after every cut. `_Surface.update` now applies the base's changed elements
  (the watch's keys, records read through the public queries) to the existing surface as a `MeshDelta`, and the provider
  says so (`surface_topology_changed`, the H7 hook the SubD preview uses; `entry_topology_changed`, a new additive H7-E
  hook, for the base beside the view); the surface's `RenderMesh` follows through its journal. The editing view still
  rebuilds after an Undo across a topology step (it is closed for topology edits anyway).
- **Unchanged:** the editing view stays shape-only (every topology operation, the Knife included, is refused on it).

### 16.2 Choices within the decision (`PROVISIONAL` where marked)

- **Origins by position in the resolver:** the constructions (`split_face_path`, `cut_in_face`, both loop closers) pass
  interior positions on unchanged, and two interior points never share a position (an interior click snaps to an own
  point within 14 px), so a position table reaches every `split_face` call without changing a construction's signature
  (they are patched by tests and probes). The value of a closed shape therefore does not depend on the bridges (tested
  bit-exact against another bridge rule).
- **Mirror-side interior points** take the source triangle's weights on the mirror corners. The mirror face's own ear-clip
  triangulation starts at its own first corner and can take the other diagonal of a quad; on a non-planar quad the mirror
  point then lies on the mirror image of the source's drawn triangle, not on the mirror side's drawn triangle. For a
  symmetric target the mirror value is the mirrored source value (AD-025 §3) — what symmetry asks; an asymmetric target
  gets the same weights on its own mirror-side values. Found by the symmetric fuzz test; no rule changes.
- **Self-crossing points** (the run crosses itself inside a face, Artist decision 2026-09-30): the blend of the two trail
  points the crossing lies between. Inside one triangle this equals the barycentric rule (tested); across a fold of the
  drawn triangulation it is the straight blend between those two points, not the piecewise value at the crossing.
- **Item 7 of the assignment (`PROVISIONAL`):** the audit's artist test asks for 3 targets, the app allows one per mesh
  until Phase 4. The automated tests run with **three layers** (two dense, one sparse); Manu's practical test uses **one
  target**. Manu can correct this in one sentence.
- **Mirror copy:** the copy's layers are independent copies (no link to the source's targets; linking is §11 "transfer",
  Phase 7).

### 16.3 Measured [C]

Container (Linux, Python 3.13, Mesa llvmpipe; `xvfb-run -a python experiments/drag_cost/probe_morph_gl.py --only-topology
--reps 7`), p50 in ms over 7 runs, each undone; "call" = the operation's own call through the app's keys (the Knife: `Enter`
after edge → two interior points → edge on the front-most quad; Extrude: the whole hold-drag-release), the cursor over the
viewport (a commit's hover refresh with a GPU pick of the new topology is part of the call); "frame" = the frame after it.
"Target" = one target with an offset on every point, dialled in at 60 %. Container timings vary up to ~2× between runs.

| Operation | head_basemesh (326 V) call / frame: no target · target | Man_With_Shoes (928 V) | gollum_20k (21,875 V) |
|---|---|---|---|
| Knife commit | 11.3 / 1.7 · 10.7 / 8.4 | 22.3 / 2.0 · 24.8 / 21.9 | 32.7 / 11.5 · 31.1 / 11.5 |
| Loop Insert | 20.2 / 1.9 · 25.2 / 15.4 | 73.0 / 2.6 · 99.8 / 39.8 | 2,903 / 11.9 · 3,027 / 112 |
| Extrude (gesture) | 9.2 / 1.7 · 9.5 / 8.8 | 24.8 / 2.1 · 24.5 / 23.7 | 17.3 / 10.5 · 18.6 / 10.8 |
| Collapse | 9.2 / 1.5 · 9.9 / 8.2 | 22.0 / 1.7 · 32.7 / 27.8 | 21.8 / 10.9 · 24.1 / 13.8 |

**Reading.** The operations cost the same with a target within the container's spread (the Core's layer writes are
µs per point, §14); what a shown target adds is the frame after (the mix surface and its render mesh take the change).
**Before the in-place patch** (§16.1, same probe, same container): the frame after was 15–20 ms on head, 49–55 ms on
body and **2.9–3.5 s on gollum_20k** for every operation. Loop Insert on gollum_20k costs ≈ 3 s without a target too
(a ring around the whole mesh; not a Phase 5 cost — noted for the viewport-performance list). A first probe run without
the cursor in the viewport made Knife and Loop Insert look +11 ms slower with a target: the hover refresh's GPU pick ran
only in the target rows; the probe now places the cursor first. **Reference PC:** the same line (`python
experiments/drag_cost/probe_morph_gl.py --only-topology`); Python there is ≈ 2× slower (REFERENCE_HARDWARE §2).

### 16.4 Tests

`tests/test_point_layers.py` (Core: the rule per layer incl. `zero` and `()`, every refusal with mesh and counters
unchanged, the length check without layers, Undo / Redo); `tests/test_mesh_change_journal.py` (T-1: the layered random
sequences call `split_face(…, origins=…)` — 75 kept calls with 129 interior points over the 12 × 25 + 300 steps, Undo to
the start and Redo to the end against the snapshot oracle); `tests/test_layer_knife.py` (T-6: open cut, closed shape
independent of the bridges bit for bit, a self-crossing run, dropped runs / a forced `check_commit` rollback / cancel /
dropped bridge candidates exact, the Core backstop drops a face point without an origin, 75 fuzzed sessions on two grids
and the head — the layered cut equals the cut without layers, every edge and interior point follows its rule, Undo / Redo
exact — and 50 fuzzed symmetric sessions with mirrored targets, the mirror edge stored the other way round at the mapped t);
`tests/test_layer_topology_ops.py` (through `Application`, plain and symmetric: Split, Edge Connect, Loop Insert, Collapse
(edge and face group), Extrude, the Knife with real picks on a warped face — the record's origin is the hit triangle's
barycentrics and the new point lies on the displaced triangle (≤ 1e-12) —, mirror copy bit-exact; the mix and the view
follow Loop Insert, Collapse, Extrude and Split on the base); `tests/test_layer_gate.py` (the declarations are the
implementations the app runs; every declared entry has its fixture; only unhandled constants stay locked);
`tests/test_morph_targets.py` (the Knife joins the refused-on-the-view cases; the randomized surface oracle now runs
`split_edge`, `split_face(…, origins=…)` and Collapse through the in-place patch and compares topology too);
`tests/test_layer_topology_ops.py` also pins the patch (the same surface mesh and render mesh, its triangles on the new
faces, through Undo / Redo; a point moved away and back in the same step; the entry surface beside the view).
**Mutation checks by hand** — each caught: the mirror split back at t = 0.5, swapped barycentric weights, a crossing that
takes its first end's origin, mirror origins not mapped through the vertex map, edges left out of the surface patch, kept
points reset to their rest position by the patch, the viewport not told about the patched topology (edit surface and
entry surface).

### 16.5 Open / next

Manu's practical test (Kurzfassung, "Praxistest Phase 5"); the reference-PC run of the probe; Loop Insert on gollum_20k
(≈ 3 s with and without a target, §16.3) for the viewport-performance list. **Next:** Phase 4 (several targets, packed storage, stage chain, morph + SubD)
or Phase 6 (skinning; the weights kind gets the Phase 5 rules for free).

## 17. Phase 4 implementation note (2026-10-27)

### 17.1 Decisions (the §11 points "evaluation location and chain" and "multi-target evaluation rules"; `PROVISIONAL` where marked)

- **Combination rule.** The additive mix `p = b + Σᵢ (wᵢ/100)·dᵢ` over the targets above 0 %; weights stay whole percent
  0–100 (the Phase 3 range; nothing clamps the sum, nothing normalizes; no correctives — out of scope). The sum runs in
  ascending `LayerId` order (fixed for a layer's life, unlike the display order, so a reorder never changes a value),
  the first term as it is: one target gives the Phase 3 values bit for bit (`b + d` at 100 %, `b + w·d` below).
- **Drift guard by construction** (audit §G "≤ 1e-6"): no point is updated incrementally. Every point whose inputs may
  have changed — the points of a target whose weight changed (sparse: only that target's points), the points the base's
  journal names, every point of a target rewritten whole — is recomputed from `b`, the weights and the offsets. The shown
  surface is a pure function of its inputs: bit-identical whatever the order or number of weight steps (tested).
- **Evaluation location: CPU, in `src/mirai/morph_mix.py`** (`MixSurface`, one evaluated `core.Mesh` per base: same IDs
  and topology, positions = the mix, patched in place from the base's journal — Phase 3/5's `_Surface` generalized). A
  shown target's offsets are cached as a dict while its weight is above 0 (memory bounded by what is dialled in). Normals
  of the evaluated surface stay the viewport's, computed from that mesh (exact, as in Phase 3).
- **Stage chain instead of the single H7 slot: `src/mirai/surface_chain.py`, above the viewport** (the viewport and the
  H7 contract are unchanged — an additive layer, easy to reverse). Stages are ordinary H7 providers in a fixed order,
  morph then SubD; a stage's input is the edit mesh or the nearest earlier stage's `surface_mesh`, so SubD's stencils run
  on the mixed cage (H5b). One wanted stage sits in the slot itself (every Phase 3 and SubD behaviour unchanged without
  the other); two sit in it as a `ChainedSurface` that forwards the output stage's H7 attributes and every stage's H7-E
  entry surfaces. A foreign host (the Morph Lab) keeps the slot. While SubD is on, the mix of an edit mesh with targets
  is kept even at 0 % (`keep_edit_surface`), so a weight step patches SubD's positions instead of switching its input.
  Skinning (Phase 6) slots in between as its own stage (audit §E: morph → skin → SubD). Picking, selection, hover and the
  tools stay on the rest-shape cage (Morph Lab 6a, §15); the SubD cage lines and the morph wire follow the mix.
- **No GPU path in this phase** (the assignment's condition "if the CPU path cannot meet fluid on head and body with 10
  targets"): in the container every head row and every body row with sparse targets is far under the bar; the only rows
  at the bar step a target that moves every body point — with one target as with ten (p95 16.6 / 16.7 ms [C]), Phase 3's
  single-target cost, i.e. the viewport's per-vertex patch, not the multi-target mix. That row is probably over the bar
  on the reference PC, which decides it (§17.3); this is a deliberate agent decision against building the GPU path now
  (`PROVISIONAL`, for Manu / a review to overturn). A vertex-shader blend would not carry the two other consumers of the mix: SubD needs
  the mixed cage on the CPU (stencils), and the wire and the Production shader's flat shading read positions on the CPU
  (`edge_segments`, the face-data rows with their corner positions), so the blend would have to be duplicated into three
  paths with approximate normals. Alternatives kept for the trigger (a reference-PC row over the bar): (a) GPU blend of
  the morph-only surface (offsets in a buffer texture, weights as uniforms, glTF-style normal deltas; CPU `morph_mix` as
  the reference); (b) a bulk path in `RenderMesh._sync_geometry` for a large moved share (the shared bottleneck of every
  whole-region move); (c) SubD stencils on the GPU. Built instead (the shared bottleneck, §15.3): the SubD provider
  reports only the derived vertices that moved after a full stencil pass (a regional move no longer patches the whole
  surface; head 15 % + SubD 56 → 22 ms p50 [C]), `update_vertex_normals` without a tuple per face (same arithmetic), and
  the inlined mix loop.
- **Packed storage (the Core internals, go given):** built, because the sparse dicts miss the budget for dense targets
  (50 dense at 20k: 204 MiB, §17.3). `src/core/layer_storage.py`: one append-only `LayerSlots` map per mesh (`VertexId` →
  slot, never freed or reused, so a value array held by a record or a delta keeps its meaning without a journal of its
  own) and per layer a `PackedValues` (three float64 per slot + a presence byte, a `MutableMapping` with dict semantics,
  values bit-exact). Behind the unchanged API; every existing layer test and the T-1 / T-2 oracles unchanged and green;
  CORE_V1_FREEZE §7.1 entry of the same date.
- **App** (names, keys, texts `PROVISIONAL`): `MAX_TARGETS = 64` (above the audit's 20–50); a **current target** per object
  (view state, not saved: the one Tab, `N`, `+`/`-`, rename and delete act on), a new target becomes current, a deleted one
  hands over to the next in the list; `Shift+N` / `Alt+N` next / previous (free in every app context, in the window keys
  and the Morph Lab's — tested); with the editing view open the switch re-derives the view as `b + dᵢ` of the new target
  (`TargetView.retarget`, positions only). A weight per (object, target), view state; a deleted target's weight goes with
  it and does not come back on Undo. HUD: the "Morph" row is the current target (with `i/n`), a "Targets" row lists every
  target with its weight, the current one in brackets (from two targets; a window of eight around the current one).
  `M` sends only the current target (the Lab knows one). Save / load, Apply transform, mirror copy and every Phase 5 tool
  already handled any number of layers; the tests now run them with three app targets dialled in.

### 17.2 What was built

`src/core/layer_storage.py` (new), `src/core/mesh.py` (packed values, `PackedValues.mapped` for `map_vector_layers`,
`layer_storage_bytes`); `src/mirai/morph_mix.py` (new: the rule, `evaluate` as the reference, `MixSurface`);
`src/mirai/surface_chain.py` (new); `src/mirai/morph_targets.py` (provider with weights and the current target per object,
the switch keys, `TargetView.retarget`, `MorphDisplay` as a chain stage); `src/mirai/subdivision/preview.py` (the chain hook,
the changed-only report); `src/mirai/application.py` (lifecycle on the current target, `step_morph_target`, the chain,
`morph_targets_text`); `src/hud.py` (the "Targets" row); `src/morph_bridge.py` (the current target);
`src/viewport/derived.py` (vertex normals); `experiments/drag_cost/probe_morph_gl.py` (`--only-phase4`, `--memory`).

### 17.3 Measured [C]

Container (Linux, Python 3.13.17, Xeon 2.1 GHz, Mesa llvmpipe); container timings vary up to ~2× between runs; the reference
PC runs Python ≈ 2× slower (REFERENCE_HARDWARE §2). **Lines for the reference PC:** `python
experiments/drag_cost/probe_morph_gl.py --only-phase4` (weight steps) and `python experiments/drag_cost/probe_morph_gl.py
--memory` (memory, no window).

**Memory and journal** (`--memory`; traced memory of the layer values after filling 10 / 50 targets with offsets on 15 % —
each target its own patch — or 100 % of the points; "write" = one dense target rewritten per element under one recording;
"bulk" = `map_vector_layers` of every target under one recording plus five watches, the Apply-transform write; timings
untraced):

| Case | dicts (before): held · write · bulk | packed (Phase 4): held · write · bulk | journal of the bulk write |
|---|---|---|---|
| gollum_20k, 10 × 15 % | 5.7 MiB · 27 ms · 25 ms | 4.2 MiB · 66 ms · 58 ms | 10 whole-layer records, 0 per element; Undo < 0.1 ms |
| gollum_20k, 10 × 100 % | 40.9 MiB · 25 ms · 216 ms | 7.5 MiB · 64 ms · 93 ms | 10 / 0 |
| gollum_20k, 50 × 15 % | 28.3 MiB · 33 ms · 239 ms | 25.7 MiB · 60 ms · 466 ms | 50 / 0 |
| **gollum_20k, 50 × 100 %** | **204.4 MiB** · 30 ms · 752 ms | **29.7 MiB** · 67 ms · 532 ms | 50 / 0; kept 27.7 MiB (the old buffers) |
| gollum, 10 × 15 % | 22.7 MiB · 103 ms · 126 ms | 18.0 MiB · 287 ms · 271 ms | 10 / 0 |
| gollum, 10 × 100 % | 163.5 MiB · 203 ms · 1.18 s | 30.1 MiB · 384 ms · 0.47 s | 10 / 0 |
| gollum, 50 × 15 % | 113.3 MiB · 131 ms · 0.92 s | 101.3 MiB · 478 ms · 1.91 s | 50 / 0 |
| gollum, 50 × 100 % | 817.5 MiB · 155 ms · 4.18 s | 118.6 MiB · 515 ms · 2.85 s | 50 / 0 |

**Verdict:** the budget (50 targets ≤ 50 MB at 20k) holds for sparse and dense targets with packed storage (25.7 / 29.7
MiB); the dicts missed it for dense ones (204 MiB). A packed layer costs 25 bytes per slot whatever its occupancy, and
slots are shared, so 50 sparse targets on different regions cost about as much as 50 dense ones (a sparse layer below
≈ 13 % occupancy would be smaller as a dict — not worth a second representation now). The price is per-element access:
≈ 0.3 µs per read instead of ≈ 0.04 µs (a whole dense target written point by point 2–3× slower; the editing view's
commit writes only the touched points, 36 in §15.3); bulk maps of dense layers got faster (whole buffers), of sparse
layers slower (every slot is visited). The journal stays O(layers) for bulk writes (whole-layer records, no per-element
records), Undo is a buffer swap.

**Weight step** (`--only-phase4`, 200 steps per row; the hold-N step of the current target, every other target at 50 %;
p50 / p95 ms; the bar 16.7 ms p95 applies to head and body on the reference PC):

| Asset | targets × offsets | no SubD | + SubD level 2 (the chain) |
|---|---|---|---|
| head_basemesh (326 V) | 1 × 15 % | 0.88 / 1.27 | 21.4 / 31.1 |
| | 1 × 100 % | 2.74 / 4.29 | 55.3 / 89.1 |
| | 10 × 15 % | 0.83 / 1.13 | 21.2 / 31.7 |
| | 10 × 100 % | 3.48 / 5.29 | 62.3 / 99.9 |
| Man_With_Shoes (928 V) | 1 × 15 % | 1.58 / 2.41 | 50.5 / 74.9 |
| | 1 × 100 % | 9.16 / 16.6 | 185 / 260 |
| | 10 × 15 % | 2.29 / 3.14 | 66.2 / 98.8 |
| | 10 × 100 % | 11.0 / 16.7 | 186 / 260 |
| gollum_20k (21,875 V) | 1 × 15 % | 36.1 / 55.2 | SubD refuses (> 25,000 faces at level 1) |
| | 1 × 100 % | 252 / 342 | — |
| | 10 × 15 % | 44.6 / 67.1 | — |
| | 10 × 100 % | 376 / 450 | — |

**Reading.** Ten targets cost about what one costs: a step touches only the stepped target's points, the other targets
add a dict lookup per point and term. Head is far under the bar in every row (≤ 5.3 ms p95 in the container, ≈ 11 ms
expected on the reference PC). Body with sparse targets likewise (≤ 3.2 ms); stepping a target that moves every body
point is at the bar in the container with one or ten targets (p95 16.6 / 16.7 ms) — the same cost Phase 3 measured for
one dense target (§15.3: 7.3 / 10.4 ms; this run is noisier) — and therefore probably over it on the reference PC: the
cost is the viewport's per-vertex patch of 928 moved points, not the mix (profiled: the evaluation ≈ ⅓ before the
inlined loop). gollum_20k stays "usable, not fluid" (H5c) with sparse targets and slow with dense ones. **Morph + SubD**
costs what SubD costs for a regional move of the cage: the viewport patches every derived vertex the move reaches (head
level 2: 5,184 faces; body level 2: 14,816) — before the changed-only report every step patched the whole derived surface
(head 15 %: 56 → 21 ms p50). It is not fluid on body; whether head is (21 / 31 ms in the container) only the reference PC
can say. The remedies are the alternatives of §17.1; their trigger is the reference-PC run.


### 17.4 Tests

`tests/test_morph_multi.py` (32): keys free in every context, the window and the Lab; lifecycle of three targets with the
current target and exact Undo / Redo; the cap; weights per target and tap `N` per target; save → load bit-exact with four
reordered targets (export and JSON text); the editing view per target (= `b + dᵢ`, switching in the view, a gesture writes
only the current target, Undo); the randomized oracle (260 steps: weight steps on random targets, base moves, offset
writes, bulk map, layer add / remove / reorder, deletions, `split_edge`, `split_face(…, origins=…)`, Collapse, Undo /
Redo — bit-exact against `evaluate`, ≤ 1e-12 against an independent `math.fsum`, a fresh evaluation bit-identical, rebuilt
only when the mesh lost every target); order independence (six permutations after 150-step random walks, bit-identical);
a weight step touches only its target's points; one target = Phase 3 bit for bit; morph + SubD = SubD of the mixed cage
from scratch (≤ 1e-12, through weight steps without a SubD rebuild, a base edit, a topology edit, Undo / Redo), the slot
rules (SubD alone, mix alone, foreign host), SubD on the editing view with the mixed base beside it; every Phase 5
declared operation (Split, Edge Connect, Loop Insert, Collapse, Extrude; plain and symmetric) and the Knife with three app
targets dialled in — rule, shown mix = definition before, after, after Undo / Redo; Apply transform and mirror copy with
three targets (world mix within 1e-12, the copy's mix mirrored bit for bit); HUD rows; the bridge.
`tests/test_layer_storage.py` (5, the storage itself). Two Phase 3 tests changed with the decided behaviour (one target per
mesh, the slot taken by whoever came first). **Mutation checks by hand** — each caught: the sum in display order, a target
going to 0 % not recomputing its points, offset writes not recomputing their points, a whole-layer rewrite not reloading
the cache, the chain feeding the edit mesh to SubD, the view not following a target switch, a deleted slot keeping its
floats, a copy sharing the buffer.

### 17.5 Open / next

Manu's practical test (Kurzfassung, "Praxistest Phase 4"); the reference-PC run of `--only-phase4` and `--memory` (it
decides whether the GPU / bulk-patch alternatives of §17.1 are needed); morph + SubD is as fluid as the SubD preview's own
regional moves (the per-vertex viewport patch of the derived surface). **Next:** Phase 6 (skinning; the weights kind, a
stage between morph and SubD). The chain and the evaluation rule are additive and reversible (no viewport change), so an
independent review is not needed for them.

---

## Kurzfassung für Manu (Deutsch)

**Worum es geht:** Damit Morph-Ziele später Topologie-Änderungen überleben, speichert das Mesh pro Ziel nur, wie weit jeder
Punkt von der Basis abweicht (statt einer ganzen Mesh-Kopie — passt zu deiner Antwort J-3 „relativ“). Jedes Werkzeug, das
einen Punkt erzeugt oder zusammenführt, gibt ihm im selben Moment seinen Wert; Undo, Abbrechen und Speichern laufen wie bei
den Positionen. Die unabhängige Review ist gelaufen („annehmen mit Änderungen“) und eingearbeitet. Sichtbar ändert sich für
dich erst mit dem ersten Ziel in der App.

**Deine Entscheidungen** (je eine Zeile; „ja“ = Empfehlung) — **beantwortet am 2026-10-27: „ja“ zu H1–H5 und C-1.**

- **H1** Solange ein Mesh Ziele hat: Löschen, Auflösen, Vertex Connect, Cap, alle Verschiebe-/Glätt-Werkzeuge und
  „Transform übernehmen“ erlaubt; Split, Connect Edges, Loop Insert, Knife, Extrude, Collapse und Spiegelkopie mit Meldung
  gesperrt, bis sie einzeln freigegeben werden? — *ja / alles sperren / alles sofort*
- **H2** Ein neuer Punkt (z. B. Loop Insert) bewegt sich im Ziel mit seinen Nachbarn mit (wie Blender; in stark gebogenen
  Stellen evtl. kurz nachformen) — oder bleibt er unbewegt (Delle)? — *ja / unbewegt*
- **H3** Beim Zusammenführen (Collapse) bekommt der übrige Punkt den Mittelwert der Ziel-Bewegungen. Reicht das? — *ja /
  ich brauche etwas anderes (dann beschreib kurz, was)*
- **H4** Ein Ziel bearbeitest du weiter daneben wie im Morph Lab (Form am Ziel, Topologie nur an der Basis) — oder an Ort
  und Stelle mit Ziel-Umschalter (Blender-Art)? — *ja / an Ort und Stelle*
- **H5a** Erst Topologie-Änderungen mit Zielen, dann das Rig? — *ja / Rig zuerst*
- **H5b** Morph und SubD zusammen sehen erst, wenn es mehrere Ziele gibt? — *ja / früher*
- **H5c** Flüssig auf Kopf und Körper, auf gollum_20k vorerst nur „benutzbar“? — *ja / auch 20k flüssig*
- **C-1 (Bestätigung)** Drehst oder skalierst du das ganze Mesh in `1`/`2`/`3`, bleiben die Ziel-Bewegungen, wie sie waren;
  einen Charakter mit Zielen drehst oder skalierst du in `4` und übernimmst den Transform (`Strg+A`) — das nimmt die Ziele
  mit, ab dem ersten Ziel in der App. — *ja / anders*

**Zur Kenntnis (keine Frage):** Re-Symmetrize gleicht nur die Basis an, nicht die Ziele.

**Phase 3 ist gebaut (2026-10-27): das erste Morph-Ziel in der App.** Praxistest (ca. 20–30 Minuten), Annahmen zum
Korrigieren in einem Satz: das Ziel wird daneben bearbeitet wie im Morph Lab, die Kamera springt mit (gleiche Stelle am
Bildschirm), das Gewicht ist reine Ansicht, Tasten sind Vorschläge.

**Wie es zusammenhängt (ein Mesh, nicht zwei):** Gespeichert wird nur die Basis — ihre Ruheform und, pro Punkt, wie weit
er im Ziel davon abweicht (der Abstand). Links steht immer die Basis: bei 0 % die Ruheform, bei einem Gewicht die Mischung
Ruheform + Gewicht × Abstand. Rechts steht nur während `Tab` eine **Arbeitskopie**: Ruheform + voller Abstand, also das Ziel
bei 100 % — egal, welches Gewicht eingestellt ist. Sie ist nur zum Formen da und wird nie gespeichert: was du an ihr bewegst,
wird nach jeder Geste als neuer Abstand in die Basis geschrieben (ein `Strg+Z`), und die Kopie verschwindet beim nächsten
`Tab`. Gleich aussehen tun beide nur bei 100 %. Änderst du links die Ruheform, behalten die Punkte ihren Abstand — das Ziel
geht mit. Drahtgitter folgt der Mischung (seit deiner Rückmeldung), Auswahl und Hover bleiben auf der Ruheform.

`python src/main.py` (Start: Head-Basemesh)

1. **Ziel anlegen.** `Strg+N` — die HUD-Zeile „Morph“ zeigt `Target 1 · 0 % · base`. `Strg+Shift+N` gibt ihm den nächsten
   Namen (Smile, Blink, …); `Strg+Z` / `Strg+Y` gehen Schritt für Schritt zurück und vor.
2. **Ziel formen.** In `1` ein paar Punkte am Mund wählen, `Tab`: das Ziel steht neben der Basis, die Kamera springt mit,
   die Auswahl bleibt. Formen mit allem, was die App hat: `W`/`E`/`R`, Tweak (`Strg`+Ziehen), Soft (`O`), Symmetrie
   (`Shift+S` vorher an der Basis), `S` Smooth. Jede Geste ist **ein** `Strg+Z`. Probier `C`, `Entf`, `T`: die Statuszeile
   sagt „on the base only“.
3. **Mischen.** `Tab` zurück zur Basis. `N` halten und die Maus nach links/rechts ziehen = Gewicht; `N` antippen = 0 % ↔
   zuletzt; `+`/`-` 10 %, mit `Shift` 1 %, `Alt+` / `Alt-` 100 % / 0 %. Auswahl und Hover liegen auf der Ruheform (wie im
   Lab). Auch während du am Ziel arbeitest (`Tab`), zeigt die Basis daneben die Mischung — Mausrad zurück, dann siehst du beide.
4. **Basis ändern.** An der Basis Punkte verschieben: das Ziel geht mit (relativ, J-3). Ein Loch mit `Entf`, Kanten mit
   Rücktaste auflösen: das Ziel bleibt auf den übrigen Punkten. `C`, `T`, `Shift+C`, `I` an der Basis: gesperrt mit Meldung
   (bis Phase 5).
5. **Drehen und übernehmen.** In `4` das Objekt mit `E` drehen und mit `R` skalieren, dann `Strg+A`: die Mischung sieht danach
   gleich aus. Gegenprobe: in `1` alles wählen und drehen — die Ziel-Bewegungen bleiben in ihrer alten Richtung (C-1).
6. **Speichern.** `Strg+S`, Fenster schließen, die Szene über `Leertaste` wieder laden: das Ziel ist da (Gewicht 0 %).
7. Optional: `python src/main.py examples/meshes/gollum_20k.obj` — benutzbar, nicht flüssig: ein kleines Ziel geht, ein Ziel
   über das ganze Mesh macht jeden Gewichtsschritt langsam; `Tab` dauert dort etwa eine Sekunde.
8. Optional auf deinem PC: `python experiments/drag_cost/probe_morph_gl.py` und die Ausgabe in den Chat (die 16,7-ms-Grenze
   für Kopf und Körper kann nur dein PC bestätigen).

| Punkt | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz |
| --- | --- | --- |
| Ziel anlegen / umbenennen / löschen (1) | | |
| Ziel daneben formen, Kamera springt mit (2) | | |
| Gewicht mit `N` ziehen / antippen, `+`/`-` (3) | | |
| Mischung an der Basis, auch während du am Ziel formst (3) | | |
| Basis ändern, Löschen/Auflösen, Sperren (4) | | |
| Drehen + `Strg+A`, C-1 (5) | | |
| Speichern / Laden (6) | | |
| Tasten (`Strg+N`, `Tab`, `N`, `+`/`-`) | | |

### Praxistest Phase 5: Topologie mit Morph-Ziel (ca. 20–30 Minuten)

**Phase 5 ist gebaut (2026-10-27):** an der Basis gehen jetzt auch mit Ziel Split, Connect Edges, Loop Insert (`I`),
Knife, Extrude (`T`), Collapse (`Shift+C`) und die Spiegelkopie (`Shift+M`) — einzeln, mit Symmetrie gespiegelt. Ein
neuer Punkt bekommt im Ziel den Abstand, der zwischen seinen Nachbarn liegt (H2 „mitgehen“); ein Knife-Punkt in einer
Fläche genau den Abstand an der Stelle, an der du geklickt hast; ein zusammengeführter Punkt den Mittelwert (H3).
Topologie weiterhin nur an der Basis, die Arbeitskopie (`Tab`) bleibt zum Formen.

**Annahmen zum Korrigieren in einem Satz:** (a) du testest mit **einem** Ziel — die App erlaubt bis Phase 4 nur eines; die
automatischen Tests laufen mit drei; (b) in stark gebogenen Stellen kann ein neuer Loop kurz nachgeformt werden müssen
(H2); (c) die Spiegelkopie bekommt eine eigene, unabhängige Kopie des Ziels (keine Verbindung zum Original).

`python src/main.py` (Start: Head-Basemesh)

1. **Vorbereiten.** `Strg+N`, ein paar Punkte am Mund und an einem Auge wählen, `Tab`, ein Lächeln und ein halbes
   Zwinkern formen (gern mit Soft `O`; mit `Shift+S` vorher an der Basis auch symmetrisch), `Tab` zurück. `N` halten und
   die Maus ziehen, bis das Ziel bei etwa 60–100 % deutlich zu sehen ist.
2. **Loop Insert.** `2`, eine Kante quer zum Augen- oder Mundloop, `I`: der neue Loop sitzt im Ausdruck, ohne Delle;
   `Tab` zeigt ihn auch in der Arbeitskopie. `Strg+Z` / `Strg+Y`.
3. **Knife.** Nichts auswählen, `C`: Kante → zwei Klicks in eine Fläche → Kante, `Enter`. Dann eine geschlossene Form in
   einer Fläche (drei Klicks hinein, den ersten wieder anklicken, `Enter`). Die neuen Punkte liegen auf der Ausdrucksform.
4. **Extrude.** `3`, eine oder zwei Flächen im Mundwinkel, `T` halten und ziehen: der Deckel nimmt den Ausdruck mit, die
   Seitenwände verbinden.
5. **Collapse und Split.** `Shift+C` auf eine Kante im Loop: der Punkt in der Mitte bekommt den Mittelwert. `C` auf einer
   Kante (Split) und auf zwei gegenüberliegenden Kanten (Connect).
6. **Symmetrie.** Mit `Shift+S` (X) an der Basis 2–5 auf einer Seite wiederholen: die Gegenseite folgt gespiegelt, das
   Ziel bleibt spiegelbildlich, wenn du es symmetrisch geformt hast.
7. **Spiegelkopie.** In `4` den Kopf mit `W` zur Seite schieben, `Shift+M` → *Mirror copy X = 0*: die Kopie trägt das Ziel
   gespiegelt: die Kopie ist danach gewählt, `1` macht sie zum bearbeiteten Objekt, `N` halten + Maus blendet ihr Ziel ein.
8. **Undo und Speichern.** Mit `Strg+Z` bis zum Anfang zurück und mit `Strg+Y` wieder vor; `Strg+S`, Fenster schließen,
   über `Leertaste` laden: Ziel und neue Loops sind da.
9. Optional: `python src/main.py examples/meshes/gollum_20k.obj` — Knife, Extrude, Collapse mit eingeblendetem Ziel
   (der Rahmen danach hing hier vorher ~3 Sekunden, jetzt nicht mehr); Loop Insert dauert dort auch ohne Ziel ~3 Sekunden.
10. Optional auf deinem PC: `python experiments/drag_cost/probe_morph_gl.py --only-topology` und die Ausgabe in den Chat.

| Punkt | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz |
| --- | --- | --- |
| Loop Insert mit Ziel (2) | | |
| Knife mit Ziel, auch geschlossene Form (3) | | |
| Extrude mit Ziel (4) | | |
| Collapse / Split / Connect mit Ziel (5) | | |
| Symmetrisch (6) | | |
| Spiegelkopie mit Ziel (7) | | |
| Undo / Speichern / Laden (8) | | |
| Annahmen (a)–(c) | | |

### Praxistest Phase 4: mehrere Morph-Ziele (ca. 20–30 Minuten)

**Phase 4 ist gebaut (2026-10-27):** ein Mesh kann jetzt viele Ziele haben. Eines davon ist das **aktuelle** — darauf
wirken `Tab` (daneben formen), `N` / `+` / `-` (Gewicht), Umbenennen und Löschen. Jedes Ziel hat sein eigenes Gewicht;
die Basis zeigt die Summe aller eingestellten Ziele (Ruheform + Gewicht₁ × Abstand₁ + Gewicht₂ × Abstand₂ + …). Mit der
SubD-Vorschau (`V`) siehst du jetzt die geglättete Mischung — Morph und SubD zusammen.

**Annahmen zum Korrigieren in einem Satz** (alles `PROVISIONAL`):
(a) Tasten: `Shift+N` nächstes Ziel, `Alt+N` voriges; ein neues Ziel (`Strg+N`) wird sofort das aktuelle.
(b) HUD: Zeile „Morph“ = das aktuelle Ziel (Name · Gewicht · Basis/Arbeitskopie · Nummer, z. B. `2/3`); Zeile „Targets“
    = alle Ziele mit ihrem Gewicht, das aktuelle in `[Klammern]` (erst ab zwei Zielen; ab neun ein Ausschnitt um das aktuelle).
(c) Die Mischung ist eine einfache Summe: zwei Ziele auf denselben Punkten bei 100 % addieren sich; nichts wird begrenzt
    oder normiert. Gewichte sind reine Ansicht (nicht gespeichert); löschst du ein Ziel, ist sein Gewicht weg — `Strg+Z`
    bringt das Ziel zurück, aber bei 0 %.
(d) Morph + SubD: die glatte Fläche und die SubD-Käfiglinien folgen der Mischung; Auswahl, Hover und die Werkzeuge bleiben
    auf der Ruheform (wie bisher). Steht SubD an, hält die App die Mischung auch bei 0 % bereit, damit Gewichtsschritte
    nicht jedes Mal die SubD-Fläche neu aufbauen.
(e) `M` (Morph Lab) schickt nur das aktuelle Ziel (das Lab kennt eines).
(f) Höchstens 64 Ziele pro Mesh.

`python src/main.py` (Start: Head-Basemesh)

1. **Drei Ziele anlegen.** `Strg+N`, `Strg+Shift+N` (→ „Smile“); `Strg+N`, `Strg+Shift+N` (→ „Blink“); `Strg+N`,
   `Strg+Shift+N` (→ „Jaw open“). Die HUD-Zeile „Targets“ zeigt alle drei, das aktuelle in Klammern. `Shift+N` / `Alt+N`
   wechseln; `Strg+Z` / `Strg+Y` gehen Schritt für Schritt (Anlegen und Umbenennen sind je ein Schritt).
2. **Jedes Ziel daneben formen.** Ziel wählen (`Shift+N`), Punkte am Mund wählen, `Tab`, ein Lächeln formen (gern mit Soft
   `O`). **In der Arbeitskopie bleiben** und `Shift+N` drücken: die Kopie zeigt jetzt das nächste Ziel („Blink“) — ein Auge
   halb schließen; noch einmal `Shift+N` („Jaw open“) — den Mund öffnen. `Tab` zurück zur Basis. Jede Geste ist ein
   `Strg+Z` und ändert nur das Ziel, das die Kopie gerade zeigt.
3. **Mischen.** An der Basis: „Smile“ wählen, `N` halten + Maus = 60 %; `Shift+N` → „Blink“ 100 %; „Jaw open“ 30 %. Die
   Basis zeigt alle drei zusammen; `N` antippen schaltet nur das aktuelle Ziel aus und wieder ein. Fühlt sich das
   Ziehen flüssig an, auch mit drei eingestellten Zielen?
4. **Morph + SubD.** `V` (glatte Fläche + Käfig), dann wieder Gewichte ziehen: die glatte Fläche zeigt die Mischung. `V`
   weiter (Isolinien), `Strg+3` (Stufe 3). Auch `Tab` mit SubD: die Arbeitskopie wird geglättet, die Basis daneben zeigt
   die Mischung. Ist das das Bild, das du erwartet hast? Fühlt sich das Ziehen mit SubD noch brauchbar an?
5. **Topologie mit mehreren Zielen.** Mit eingestellter Mischung an der Basis: `2`, eine Kante quer zum Augenloop, `I`
   (Loop Insert); Knife (`C`) durch eine Fläche an der Wange; `Shift+C` auf eine Kante. Alle Ziele gehen mit, keine
   Delle; `Tab` + `Shift+N` zeigt den neuen Loop in jedem Ziel.
6. **Löschen und Undo.** Ein Ziel wählen, `Alt+Shift+N` (löscht das aktuelle), dann `Strg+Z`: es ist wieder da (bei 0 %).
   Mit `Strg+Z` weiter bis zum Anfang, mit `Strg+Y` wieder vor.
7. **Speichern.** `Strg+S`, Fenster schließen, über `Leertaste` laden: alle Ziele sind da (Gewichte 0 %, aktuelles = das erste).
8. Optional: `python src/main.py examples/meshes/gollum_20k.obj` — mehrere kleine Ziele sind benutzbar, ein Ziel über das
   ganze Mesh macht jeden Gewichtsschritt langsam (wie bisher); SubD lehnt dort schon Stufe 1 ab (zu viele Flächen).
9. Optional auf deinem PC (die 16,7-ms-Grenze für Kopf und Körper kann nur dein PC bestätigen), die Ausgaben in den Chat:
   `python experiments/drag_cost/probe_morph_gl.py --only-phase4` und `python experiments/drag_cost/probe_morph_gl.py --memory`.

| Punkt | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz |
| --- | --- | --- |
| Ziele anlegen / umbenennen / löschen, Undo (1, 6) | | |
| Wechseln mit `Shift+N` / `Alt+N`, auch in der Arbeitskopie (1, 2) | | |
| HUD-Zeilen „Morph“ und „Targets“ (1, 3) | | |
| Mischen: Summe, `N` pro Ziel, flüssig? (3) | | |
| Morph + SubD zusammen, flüssig genug? (4) | | |
| Topologie mit mehreren Zielen (5) | | |
| Speichern / Laden (7) | | |
| Annahmen (a)–(f) | | |
