# AD-025 — Topology Identity, Provenance and Point Layers (ARCH-02)

**Status:** PROPOSED (2026-10-27); **revised the same day after the independent review**
[CLAUDE-001](../archive/deformation/reviews/AD-025_REVIEW_CLAUDE_001.md) (ACCEPT WITH CHANGES, no blocker; the disposition
of every finding is in §13). Decision preparation, docs only: nothing in `src/`, `tests/` or `experiments/` is changed.
**Go for the Phase 2 Core change: Manu, 2026-10-27** ("I give the Go for the Phase 2 Core Changes"). Still open: H1–H5 (the mechanism takes them as parameters with `PROVISIONAL`
defaults, §10, Kurzfassung).
**Gate:** [ROADMAP ARCH-02](ROADMAP.md#arch-02--topology-identity--provenance--remapping); audit §G Phase 1.
**Mode (M5):** Discovery → decision preparation. Implementation starts with Phase 2 (§7–§9).
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
| Split (`C`, 1 edge: `split_edge(e, 0.5)`) | both ends; both faces (boundary +1) | +1 V, +2 E / `e` | new = (1−t)·v0 + t·v1, `(v0, v1)` as stored — the position's expression (Phase 2) | locked until Phase 5 |
| Edge Connect, Loop Insert (`split_edge(e, 0.5)` per kept edge, then `connect_vertices` per face) | edge ends; faces without a chord | per split as Split; per chord +1 E, +2 F / the face | midpoints as Split; chords none | locked until Phase 5 |
| Vertex Connect (`connect_vertices`) | all vertices, untouched edges | +1 E, +2 F / the face | none (no vertex) | allowed |
| Knife (kept `split_edge(e, t)`, `split_face(f, a, b, positions)`; closed shape = two calls) | boundary vertices and edges of the cut faces | edge points as Split; per call k V, k+1 E, 2 F / the parent (an intermediate face is burned) | edge points (1−t, t) (Phase 2; a split of an already split piece stays linear along the original edge). Interior points: the Knife passes their origin — barycentric weights of the hit triangle over the **original** face's corners (`split_face(origins=…)`, Phase 5). Until then `split_face` with k > 0 refuses on a layered mesh. Session: `SessionStart`; a dropped candidate `revert_change`; refused commit `abandon` | locked until Phase 5 |
| Symmetric Knife (replay of kept calls) | per side as Knife | per side as Knife | source side as Knife. **Mirror side today: split at 0.5, then snap the position (F-6) — its value would be the midpoint blend.** Phase 5 splits at the mapped t (t or 1−t by edge orientation), then snaps, and mirrors the interior origins through the vertex map | locked until that fix |
| Symmetric Split / Edge Connect / Collapse / removal / Cap / Extrude coordinators | per side | per side | each side through its own primitive call; mirror values equal the mirrored source values up to rounding (positions keep their exact snap; values need none; the Collapse snap does not affect the average) | as the plain operation |
| Extrude (tool: `add_vertex` copies, walls/caps `add_face`, `remove_face`, `delete_edges` of orphans) | everything outside the region; region boundary vertices (wall bases) | +1 V per region vertex, walls, caps / region faces, inner edges, inner vertices | cap vertex = copy of its source, `origin=((v, 1.0),)`; the drag then moves positions only | locked until Extrude passes origins (Phase 5) |
| Collapse V/E/F (`collapse_elements`) | one survivor per group | other group vertices, inner edges, degenerate faces / none created | survivor = component mean of the group's **original** values, `_centroid`'s arithmetic (H3, Phase 2) | locked until Phase 5 |
| `collapse_edge` (primitive) | `v0` | `v1`, `e`, degenerate faces | (a + b)/2, the position's expression | — |
| Dissolve V/E/F (± cleanup), Delete V/E/F, Cap | everything not removed | deletions; Dissolve +1 F per region, +1 E per chain; Cap +1 F per loop | none created; values of removed vertices are deleted (journaled) | allowed |
| Move / Rotate / Scale, Tweak, Soft, Loop Slide, Smooth, Relax, Re-Symmetrize | all | positions only | untouched (edit rule, §4.3); Re-Symmetrize therefore leaves targets as they were | allowed |
| Apply transform (`apply_placement`, composite command, every baked object) | all | positions `p → to_world(p)` | vector `v → s·R·v`; weights unchanged; identity placement: nothing | locked in Phase 2; **wired with Phase 3** (§7) |
| Clear transform, object W/E/R in `4` | all | placement only | none | allowed |
| Mirror copy (menu method `mirror_copy` → `mirror_mesh`) | source unchanged | new mesh, new IDs (dense, source-ID order) | each layer copied through the index map, vector `v → H·v` | locked for a layered source until wired (Phase 5) |
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

**Phase 5 (with the Knife wiring; a second, additive Core change):** `split_face(…, origins=None)` — one `VertexOrigin`
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

**Storage:** one sparse dict per layer, Core-internal. Measured [C] [R] (dict of tuples): one layer at 15 % / 100 %
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
- **Core backstop:** `add_vertex` without an origin and `split_face` with interior points (until Phase 5's `origins=`)
  refuse on a layered mesh. The backstop catches a forgotten origin (mechanical omission); the gate catches what the Core
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
- **Phase 3 — one persistent target** (audit Phase 3). Needs H1 (the table as shipped) and H4. Includes the Apply
  transform wiring (one `map_vector_layers` call per baked object, F-7) — decided here, so `Strg+A` works with targets from
  the first app version. The editing view needs its own Undo command that writes layer values (a gesture on the view is no
  position write; F-8).
- **Phase 4** — multiple targets (audit Phase 4); the packed-storage decision belongs here.
- **Phase 5 — topology edits with targets,** one operation at a time with its acceptance test and gate lift: Split /
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

| | Decides | Lives in | `PROVISIONAL` default | Needed by |
|---|---|---|---|---|
| H1 | Which operations run while a mesh has targets | the gate table's entries (§4.4) | allowed: Delete, Dissolve, Vertex Connect, Cap, every position-only tool, Apply transform (from Phase 3); locked with a message: Split, Edge Connect, Loop Insert, Knife, Extrude, Collapse, mirror copy — lifted one by one in Phase 5 | Phase 3 |
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
- **Evaluation location and chain:** CPU or GPU, the stage chain that replaces the single H7 slot, SubD on evaluated
  positions, normals of the evaluated surface.
- **Multi-target evaluation rules:** combination, correctives, normalization, clamping, weight ranges, the drift guard
  of incremental sums.
- **Transfer between different meshes:** retopology, import, linking a mirror copy's targets to its source's, morph
  export (OBJ / glTF).
- **Editing-view mechanics** (H4 design: how a gesture on the view becomes one Undo step on the offsets; writing back only
  touched points), editing on a deformed pose, symmetric target editing.
- **Weights as document state / animation** (`Scene.morph_targets` stays reserved, `null`).
- A merge rule other than the average (H3 alternative); face- and corner-domain layers; packed storage (Phase 4).

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

---

## Kurzfassung für Manu (Deutsch)

**Worum es geht:** Damit Morph-Ziele später Topologie-Änderungen überleben, speichert das Mesh pro Ziel nur, wie weit jeder
Punkt von der Basis abweicht (statt einer ganzen Mesh-Kopie — passt zu deiner Antwort J-3 „relativ“). Jedes Werkzeug, das
einen Punkt erzeugt oder zusammenführt, gibt ihm im selben Moment seinen Wert; Undo, Abbrechen und Speichern laufen wie bei
den Positionen. Die unabhängige Review ist gelaufen („annehmen mit Änderungen“) und eingearbeitet. Sichtbar ändert sich für
dich erst mit dem ersten Ziel in der App.

**Deine Entscheidungen** (je eine Zeile; „ja“ = Empfehlung):

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
