# AD-025 — Topology Identity, Provenance and Point Layers (ARCH-02)

**Status:** PROPOSED (2026-10-27). Decision preparation, docs only: nothing in `src/`, `tests/` or `experiments/` is
changed. Independent review pending (§13). Artist decisions H1–H5 stay open; the mechanism takes them as parameters with
`PROVISIONAL` defaults (§10, Kurzfassung).
**Gate:** [ROADMAP ARCH-02](ROADMAP.md#arch-02--topology-identity--provenance--remapping); audit §G Phase 1.
**Mode (M5):** Discovery → decision preparation. Implementation is Phase 2 (§7–§9).
**Input:** [mesh architecture audit 2026-10-27](../research/deformation/MESH_ARCHITECTURE_AUDIT_2026-10-27.md) (§C–§H and
the Phase 0 addendum). Every claim taken from it was re-verified against the code at `a53c14f` (Phase 0 merged); where
this AD differs from the audit, it says so (§1, last paragraph).
**Builds on:** AD-001 / AD-002 ([V1_CORE](V1_CORE.md)), [AD-021 §4.9](AD-021-OBJECT-COMPONENT-MODEL.md) (Mesh = rest shape;
ID-keyed deformation data lives with the Mesh), [AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) §2 H1 / §9
(journal, exactness contract), [AD-REGIONS-01](AD-REGIONS-01-FACE-REGIONS-STORAGE.md) (§1.6 inheritance, §2 whole-value
cost), [AD-SYM-03](AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) §2.5 D-b (declaration = support, fail-closed),
[AD-017](AD-017-CUT-ENGINE-CONTEXTUAL-C.md) B5 / K1 (primitives as the provenance hook), [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §7.
Supersedes the morph part of [AD-005](AD-005-RIGGING-INTEGRATION.md) (already SUPERSEDED).
**Decided by:** Manu (H1–H5; go for the Phase 2 Core change) after the independent review; the Core change follows
CORE_V1_FREEZE §7 (§8).
**Tags:** **[V]** verified in code at `a53c14f` · **[C]** measured in the container (Linux, Python 3.13.17; throwaway
probes outside the repository, not kept — a subclass of the real `Mesh` for journal cost and memory, a pure-Python MVC
probe; the reference PC runs Python ≈ 2× slower, [REFERENCE_HARDWARE](REFERENCE_HARDWARE.md) §2) · **[RPC]** reference
PC, from repo documents · **[H]** estimate.

---

## 0. Decision in one screen

1. **Identity** keeps the AD-001 contract: IDs never reused, every ID an operation does not invalidate keeps its meaning.
2. **Origin is applied, not stored.** Each Core primitive that creates or merges a vertex knows where it came from — an
   affine combination of existing vertices — and applies that to every point layer at mutation time: `split_edge`
   (1 − t, t), `split_face` interior points by mean value coordinates over the parent face's corners in its Newell plane,
   `collapse_edge` and Collapse groups by a merge rule, `add_vertex(position, origin=…)` for tools that build geometry
   themselves (Extrude). Nothing about the origin outlives the call: no provenance store, no operation log, no listener.
3. **Point layers are owned by the Mesh and journaled per element** in the existing change journal, so Undo/Redo,
   rollback (Knife checkpoints, Extrude cancel, nested Collapse, `_mesh_transaction`) and the file come from the same
   records that already carry positions. A morph target is one vector layer of offsets keyed by the base's `VertexId`s
   (Manu's J-3: "relativ").
4. **Edit vs. frame change:** an edit (every component tool) changes rest positions and leaves offsets alone; a frame
   change (Apply transform, mirror copy) re-expresses the shape and maps vector values by its linear part.
5. **Fail-closed gate:** while a mesh has layers, an app operation runs only if it is declared layer-safe (one table,
   AD-SYM-03 D-b style); the Core backstops by refusing any vertex creation without an origin.
6. **Face regions stay as they are** (inference, AD-REGIONS-01 §1.6).
7. **H1–H5 are parameters:** H1 = the gate table's content, H2/H3 = per-layer rules, H4 = the Phase 3 editing view,
   H5 = the phase order. None of them blocks Phase 2.

## 1. Facts this AD relies on (re-verified at `a53c14f`)

| # | Fact | Where [V] |
|---|---|---|
| F-1 | Every `Mesh` mutation records, on first touch, before-records in every active `MeshChange`: position, edge `(v0, v1, faces)`, boundary, symmetry, regions. No origin, no operation parameters | `src/core/mesh.py:157`, `:316` |
| F-2 | Vertices are created only by `add_vertex` (`mesh.py:439`); `split_edge` (`:536`) and `split_face` (`:776`) call it internally. On an *edited* mesh the only direct tool caller is Extrude (`extrude.py:229`); the other callers build new meshes (`scene_factory`, `object_mirror.mirror_mesh`, the SubD derived mesh `subdivision/preview.py:442`) | grep `add_vertex(` in `src/` |
| F-3 | Vertices are removed only through `_delete_vertex` (`mesh.py:733`: `collapse_edge`, Dissolve, Delete) and, for Undo / rollback / load, through `_apply_records` (`:1632`) | |
| F-4 | `split_edge` places the vertex at `a·(1−t) + b·t`, `(a, b)` = the edge's stored `(v0, v1)`; `collapse_edge` (`:599`) keeps `v0` at `(a + b) / 2` and deletes `v1`; `collapse_elements` (`core/operations/collapse.py:72`) chains `collapse_edge` and then sets the survivor to the centroid of the group's original positions | |
| F-5 | `split_face` deletes the parent before creating its k interior vertices at caller positions, no geometry check. Knife interior positions are ray hits on the viewport's triangulation (`picking.face_hit_position`; ear clipping in the Newell plane, `viewport/derived.py:105`). A closed Knife shape is two `split_face` calls, the second inside a half of the first (`knife_resolve.py`, `close_loop_with_bridges`) | |
| F-6 | The symmetric Knife replays a kept `split_edge` on the mirror edge **at t = 0.5** and then moves the vertex to the mirror position (`symmetric_knife.py:392–397`). The symmetric Split / Edge Connect coordinators split at 0.5 on both sides (`symmetric_ops.py:196`) | |
| F-7 | Apply transform writes `to_world(p)` per vertex inside one `record_mesh_change` (`scene_objects.py:405`, `application.py:1875`); a displacement maps by `delta_to_world = s·R·d` (`object_space.py`). Mirror copy builds a new mesh with `H·p` and reversed winding, new dense IDs in source-ID order (`object_mirror.py:84`) | |
| F-8 | Every app commit boundary is one journal recording: `_mesh_transaction` (`application.py:5461`), Extrude begin → commit / cancel, Knife `SessionStart` with `revert_change` checkpoints, Loop Slide and Smooth gestures, Apply transform; Collapse rolls back per group (nested) | |
| F-9 | Readers of `MeshChange` internals outside the Core: `SessionStart.unchanged()` / `.state()` (`knife_resolve.py:291`, `:302`), `regions.inherit_into`. `mesh_content` drops top-level keys ending in `_counter` (`knife_resolve.py:550`) | |
| F-10 | An edited mesh carries up to five `MeshWatch`es (render mesh, two in the pick cache, SubD preview, soft shading) plus the operation's recording; each journaled write touches every active log | `viewport/render_mesh.py:187`, `mirai/viewport/picking_cache.py:135`, `:289`, `subdivision/preview.py:289`, `soft_selection/gl_shading.py:132` |
| F-11 | Morph Lab: target = full mesh copy paired by equal IDs; any topology change switches the mix off. Manu 2026-10-17: J-3 "relativ" (the target follows later base edits), J-5 "daneben", the weight is no Undo step and not saved, picking on the rest shape "hilft" | [Morph Lab README](../../experiments/morph_lab/README.md) |
| F-12 | Triangulation is a viewport algorithm (`src/viewport/derived.py`), not a Core one | |

**Where this AD differs from the audit:** (a) the audit's Phase 5 holds "origin interpolation in the primitives"; this AD
moves the Core half into Phase 2 and keeps the product exposure staged by the gate (§7, X-11). (b) The symmetric Knife's
0.5-then-snap replay (F-6) is a tool-level case that "covered if origin is recorded at primitive level" (audit §D) does
not cover (§3, §4.4). (c) Edge Connect and Loop Insert are midpoint splits plus `connect_vertices` [V] — one row with
Split.

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
by the tool through `add_vertex(origin=…)` — and the origin is **applied** to every point layer inside the same call;
it is **not recorded**: the journal records the resulting layer values like any other write. **Edges and faces** record no
origin; face data keeps the inference of AD-REGIONS-01 §1.6; an exact face origin is available inside `split_face`,
`connect_vertices` and Dissolve if a face-domain layer is ever needed (§4.5). No element carries provenance metadata.

**Which dependent data can be invalidated?** Derived and session data — never saved, never remapped; it follows the
journal (`MeshWatch`) or is recomputed: render buffers, pick cache and screen grid, SubD derived mesh and stencils,
symmetry correspondence and completeness reports, Soft Selection weights, mask / hide sets and the selection (dead IDs
filtered), the Knife's kept-call report (one session), and from Phase 3 the evaluated (deformed) positions.

**Which dependent data must be remapped?** Persistent ID-keyed data whose meaning survives the edit: (a) **point layers**
(morph offsets now, normalized weights later), by the origin rule inside the primitives (§4.1); (b) **face regions**, by
the existing inference (unchanged); (c) the **symmetry seam**, by the coordinators' seam rules S1–S3 (unchanged). Data
held outside the mesh and keyed into it (future skin bindings, animation keys) is not remapped; a dead ID drops out.

**What minimum information must topology operations expose?** (1) Their ID-continuity contract (exists). (2) For each
vertex they create or merge, an origin rule applied to the layers in the same recording — inside the primitive, or via
`add_vertex(origin=…)` for tool-built vertices. (3) For a whole-mesh frame change, its linear map (§4.3). (4) At app level,
a declaration that the resolved operation is layer-safe (§4.4). Nothing more: no operation log, no provenance in
History, no callbacks, no parameters in the journal.

## 3. Per-operation contract

All rows run inside one journal recording (F-8): Undo/Redo is the delta, rollback is the journal, and layer writes made
by the primitives are part of both. "Gate" = the H1 default (`PROVISIONAL`, §10).

| Operation (code path) | Keeps | Creates / invalidates | Point-layer rule | Gate |
|---|---|---|---|---|
| Split (`C`, 1 edge: `split_edge(e, 0.5)`) | both ends; both faces (boundary +1) | +1 V, +2 E / `e` | new = (1−t)·v0 + t·v1, `(v0, v1)` as stored — the position's expression | locked until Phase 5 |
| Edge Connect, Loop Insert (`split_edge(e, 0.5)` per kept edge, then `connect_vertices` per face) | edge ends; faces without a chord | per split as Split; per chord +1 E, +2 F / the face | midpoints as Split; chords none | locked until Phase 5 |
| Vertex Connect (`connect_vertices`) | all vertices, untouched edges | +1 E, +2 F / the face | none (no vertex) | allowed |
| Knife (kept `split_edge(e, t)`, `split_face(f, a, b, positions)`; closed shape = two calls) | boundary vertices and edges of the cut faces | edge points as Split; per call k V, k+1 E, 2 F / the parent (an intermediate face is burned) | edge points (1−t, t); interior points mean value coordinates over the call's parent (§4.1). Session: `SessionStart`; a dropped candidate `revert_change`; refused commit `abandon` | locked until Phase 5 |
| Symmetric Knife (replay of kept calls) | per side as Knife | per side as Knife | source side as Knife. **Mirror side today: split at 0.5, then snap the position (F-6) — its value would be the midpoint blend, not the blend at the source's t.** Phase 5 splits at the mapped t (t or 1−t by edge orientation), then snaps | locked until that fix |
| Symmetric Split / Edge Connect / Collapse / removal / Cap / Extrude coordinators | per side | per side | each side through its own primitive call; mirror values equal the mirrored source values up to rounding (positions keep their exact snap; values need none) | as the plain operation |
| Extrude (tool: `add_vertex` copies, walls/caps `add_face`, `remove_face`, `delete_edges` of orphans) | everything outside the region; region boundary vertices (wall bases) | +1 V per region vertex, walls, caps / region faces, inner edges, inner vertices | cap vertex = copy of its source, `origin=((v, 1.0),)`; the drag then moves positions only | locked until Extrude passes origins (Phase 5) |
| Collapse V/E/F (`collapse_elements`) | one survivor per group | other group vertices, inner edges, degenerate faces / none created | survivor = merge rule over the group's original values (H3): `average` = component mean (`_centroid`'s arithmetic), `keep` = the survivor's own | locked until Phase 5 |
| `collapse_edge` (primitive) | `v0` | `v1`, `e`, degenerate faces | `average`: (a + b)/2 (the position's expression); `keep`: `v0`'s | — |
| Dissolve V/E/F (± cleanup), Delete V/E/F, Cap | everything not removed | deletions; Dissolve +1 F per region, +1 E per chain; Cap +1 F per loop | none created; values of removed vertices are deleted (journaled) | allowed |
| Move / Rotate / Scale, Tweak, Soft, Loop Slide, Smooth, Relax, Re-Symmetrize | all | positions only | untouched (edit rule, §4.3) | allowed |
| Apply transform (`apply_placement`, composite command) | all | positions `p → to_world(p)` | vector `v → s·R·v`; weights unchanged | locked until wired (one call; recommended with Phase 3) |
| Clear transform, object W/E/R in `4` | all | placement only | none | allowed |
| Mirror copy (`mirror_mesh`) | source unchanged | new mesh, new IDs (dense, source-ID order) | each layer copied through the index map, vector `v → H·v` | locked for a source with layers until wired |
| Undo / Redo (`apply_delta`) | exact | — | the delta's records | — |
| Load scene · OBJ import · Add Mesh · SubD derived mesh | new ID spaces | — | the scene file restores layers; the others carry none | — |
| OBJ export | — | — | rest shape only | — |

## 4. Mechanism

### 4.1 Vertex origin inside the primitives

`VertexOrigin = tuple[tuple[VertexId, float], ...]`: live source vertices with finite weights, |Σw − 1| ≤ 1e-9; `()` means
"no source" (explicit). It exists only during the call. Per layer, a new or merged vertex gets the kind's combination of
its sources' values (an absent value counts as the kind's default) — unless the layer's `new_point` rule (H2) is `"zero"`,
then nothing is stored. A result equal to the default is not stored (canonical form, §4.2).

- **`split_edge(e, t)`:** origin `((v0, 1−t), (v1, t))` with the stored ends. Vector values use the position's own
  expression `a·(1−t) + b·t` per component. Cost [C]: +0.01 / +0.04–0.06 ms per split with 10 / 50 layers at 15 %
  occupancy (0.024–0.028 ms without layers, 20k and 87.5k alike).
- **`split_face(f, a, b, positions)`:** for each interior position x: mean value coordinates (Floater 2003; Hormann &
  Floater 2006 for arbitrary simple polygons) over the parent's boundary corners, taken before the parent is deleted.
  **Non-planar faces:** corners and x are projected into the parent's Newell plane (unit Newell normal — the plane
  `FaceFrame` and the viewport triangulation use); w_i ∝ (tan(α_{i−1}/2) + tan(α_i/2)) / r_i with signed angles,
  normalized. Decided before the formula: x on a corner (r_i ≤ ε·size) → that corner; x on an edge
  (|A_i| ≤ ε·r_i·r_{i+1}, D_i < 0) → the edge blend, the same rule as `split_edge` (equal up to rounding), so an edge
  point gets the same value whichever primitive made it; a degenerate parent (Newell normal ≈ 0) → inverse-distance weights. The function is
  total: `split_face` never refuses because of layers. k = 0: no vertex, nothing to do. Measured [C]:
  - planar faces reproduce affine data to ≤ 2.4e-15 of the value spread (convex quad, concave L-hexagon, tilted
    pentagon); stable up to distance 0 from an edge (≤ 3.3e-16);
  - non-planar: MVC reproduces the projected position, not the out-of-plane part. For data that is affine in 3D the
    error grows with the warp: 2 % / 9 % / 16 % of the face's value spread at warp 0.05 / 0.2 / 0.5 (a unit quad with one
    corner lifted). **gollum_20k**, 21,875 faces: warp (max out-of-plane / face size) p50 0.36 %, p99 3.9 %, max 21 %;
    affine-data error p50 0.07 %, p99 1.8 %, max 10.7 % of the face's spread — for a 5 mm offset spread across a face,
    p99 ≈ 0.09 mm. For a smooth non-affine field both MVC and barycentric weights err by tens of percent of the spread on
    a unit quad (interpolation from 4 corners), MVC less (27–37 % vs. 33–55 %);
  - composition: the rule is per call. A Knife closed shape (two calls) equals a direct interpolation over the root face
    exactly for affine data (4e-16) and differs by ≤ 1.1 % (smooth data) / ≤ 3.0 % (random corner data) of the value
    spread. Accepted — deterministic, small — and the Knife acceptance (§9 T-6) compares with the replayed per-call rule;
  - cost: 13–16 µs per interior point (quad / 8-gon), only when layers exist.
- **`collapse_edge(e)`:** survivor by the layer's `merge` rule (H3): `"average"` → (a + b)/2 per component (the
  position's expression), `"keep"` → `v0`'s value; then `v1`'s values go with `v1`.
- **`collapse_elements`:** after the chain, each merging group's survivor gets the merge rule over the group's
  **original** values (captured before the chain, like `_centroid`): `"average"` = component mean with `_centroid`'s
  arithmetic, `"keep"` = the survivor's original value (the chain keeps it already).
- **`add_vertex(position, origin=None)`:** without layers `origin` is ignored and behaviour is unchanged. With layers an
  origin is required: `None` raises `MeshError` before any mutation, counters unchanged (the Core backstop, §4.4); `()`
  stores defaults; otherwise validated and applied.
- **`_delete_vertex(v)`:** deletes `v`'s values in every layer, journaled (invariant L1).
- No layer effect: `connect_vertices`, `add_face`, `add_edge`, `remove_face`, the face/edge part of Dissolve,
  `set_vertex_position`.

**Combination per kind.** Vector: Σ w_i·v_i per component (affine). Normalized weights (specified here, built with
skinning): sparse Σ w_i·v_i over influence keys, negative entries dropped (MVC is negative inside concave faces: down to
−0.010 on the L-hexagon [C]), renormalized to 1, empty → default.

### 4.2 Point layers owned by the Mesh

**Data model** (names `PROVISIONAL`):

- `LayerId(ElementId)` in `core/ids.py`: monotonic, never reused, counter forward only (AD-001; the `ObjectId` precedent).
- `PointLayerInfo` (frozen): `name` (non-empty, unique per mesh), `kind` (`LayerKind.VECTOR`; `WEIGHTS` reserved),
  `new_point` (`"interpolate"` | `"zero"`, H2), `merge` (`"average"` | `"keep"`, H3).
- The mesh holds `_layer_meta: tuple[tuple[LayerId, PointLayerInfo], ...]` (order = display order) and
  `_layer_values: dict[LayerId, dict[VertexId, value]]`. Vector value: `tuple[float, float, float]`, finite; default
  `(0.0, 0.0, 0.0)`.
- The Core owns the layers and does not interpret them (AD-SYM-01 §3 pattern). What a layer means — a morph target, its
  weight, which view shows it — lives in `src/mirai`. A morph target is one vector layer; its weight stays view state
  (F-11). `Scene.morph_targets` stays reserved and `null`.

**Invariants** (contract-tested): **L1** values only for live vertices and existing layers; **L2** canonical — a value
equal to the kind's default is never stored, so layer state compares as dicts and exports deterministically; **L3** vector
values are three finite floats; **L4** names unique, `LayerId`s never reused; **L5** no layers ⇔
`export_state()["point_layers"] is None`.

**Storage:** one sparse dict per layer, Core-internal. Measured [C] (dict of tuples): one layer at 15 % / 100 % occupancy
= 0.57 / 3.96 MiB at 20k, 2.14 / 16.22 MiB at 87.5k; 50 sparse targets at 20k ≈ 29 MiB, 50 dense ≈ 198 MiB. Packed
storage (an array per layer plus a slot map) is an internal change behind the same API (CORE_V1_FREEZE §7: internals
change when profiling justifies it), decided in Phase 4 against its budget (50 targets ≤ 50 MB at 20k, audit §G). A
GPU / evaluation copy is derived, never the Core's.

**API** (`PROVISIONAL`): read `point_layer_ids()`, `point_layer_info(lid)`, `layer_value(lid, vid)` (default when absent),
`layer_items(lid)` (stored values, ascending `VertexId`); write, each journaled: `add_point_layer(info) -> LayerId`,
`remove_point_layer(lid)`, `set_point_layer_info(lid, info)`, `set_point_layer_order(ids)`,
`set_layer_value(lid, vid, value)`, `map_vector_layers(m3x3)`; plus `add_vertex(position, origin=None)`.

**Journal:**

- `MeshChange.layer_meta` (`_UNSET` or the before-meta), journaled whole like `regions`; `MeshChange.layer_values:
  dict[LayerId, dict[VertexId, value | None]]`, a before-record per element on first touch (None = absent), through a
  `_touch_l(lid, vid)` helper like `_touch_v`.
- `MeshDelta.layer_meta: (before, after) | None`; `MeshDelta.layer_values: dict[LayerId, dict[VertexId, (before, after)]]`,
  differing entries only.
- `end_change`, `rollback_change`, `revert_change`, `apply_delta`, `MeshChange.is_empty`, `MeshDelta.empty` extended.
  Apply order: meta that (re)creates layers, then values, then removal of layers no longer in the meta — L1 holds after
  every apply.
- `remove_point_layer` = journaled deletion of every value plus the meta change (O(values), once; an explicit command).
- `load_state` under a journal writes only differing values, like the containers.
- Measured [C] (prototype subclass of the real `Mesh`, side table per log): `set_layer_value` 0.4–0.6 µs without a
  recording, 1.1–1.3 µs with one, 1.9 µs with three, 2.3–3.6 µs with five active logs. Rewriting one dense layer under
  one recording: 34 ms (20k) / 200 ms (87.5k); under five logs 62 / 354 ms; journal ≈ 2.7 / 10.5 MiB.
  `delete_vertices(1000)` with 50 sparse layers: 83 → 99 ms (20k), 133 → 146 ms (87.5k).

**File** — additive, no `FORMAT_VERSION` bump (precedent `"symmetry"`, `"face_regions"`): a top-level
`"layer_id_counter"` beside the other counters (so `mesh_content` and the tests' `_body` drop it like them) and
`"point_layers"`: `null` or `[{"id", "name", "kind", "new_point", "merge", "values": {"<vid>": [dx, dy, dz], …}}]` in
display order, vertex IDs ascending. `load_state` reads both with `.get` (old files: no layers, counter 1); an unknown
kind or rule, a duplicate name or a value for a missing vertex makes the file invalid (`ValueError`, fail-closed). JSON
floats round-trip exactly (Python `repr`).

**AD-023 exactness contract, point by point:** (1) counters — `layer_id_counter` only moves forward, is never in a delta,
`load_state` restores it forward; (2) journaled values — the meta like the symmetry definition, the values per element;
(3) record content — values are the stored float tuples, bit-exact; the meta keeps the order; (4) iteration order — the
order inside a value dict is not semantic: every reader is order-free or sorts, `export_state` writes ascending IDs, the
meta order is journaled, and the snapshot oracle compares exports, so it is exact; (5) rollback / abort — the same
records, no snapshot; (6) "changed?" — a layer-only change is a non-empty delta (pushes an entry, wakes the watches);
new (7) — L1–L5 hold after every primitive, apply and load.

**Consumers updated in Phase 2:** `SessionStart.unchanged()` / `.state()` include layers (F-9); `regions.inherit_into` is
unaffected; viewport, pick cache and SubD watches ignore layer slots (they draw the rest shape); a layer-only Undo must
not trigger a topology rebuild (`_apply_undo_redo`) — tested.

### 4.3 Linear-map rule: edit vs. frame change

- **Edit** — every component tool, in object space: rest positions change, offsets do not; the target is the new rest
  plus the old offset (J-3 "relativ"; Blender's relative shape keys behave the same when the basis is edited — general
  knowledge of its design, not verified against its source). Consequence: rotating or scaling the whole mesh in
  `1`/`2`/`3` leaves the expressions in their old orientation and size. That is an edit; the frame change is mode `4` plus
  Apply transform (AD-021 A-5: the level is always explicit).
- **Frame change** — the same shape in new coordinates: vector values map by the linear part M of the point map, weights
  stay. Apply transform: `p → to_world(p)`, M = s·R (`delta_to_world`), through `Mesh.map_vector_layers(M)` in the same
  recording as the positions. Mirror copy: `p → H·p`, M = H, the new mesh's layers built through the index map.
  Translation never touches offsets. Exactness: after Apply, evaluated positions equal the old world-space evaluation up
  to rounding; for axis-plane mirrors (H entries 0 / ±1) the copy is bit-exact.
- **Cost** [C]: one layer write per stored value (1.6–2.3 µs with one recording). Basemeshes (< 1k points) × 50 dense
  layers ≈ 0.1 s; gollum 87.5k × 50 dense ≈ 10 s [H, from the per-value cost]. If that matters, a whole-layer replacement
  record is the measured follow-up (not decided).

### 4.4 Operation gate (fail-closed) and Core backstop

- **Gate** (`src/mirai`, module name `PROVISIONAL` `layer_declarations.py`, beside `symmetry_declarations.py`):
  `LAYER_SAFE_OPERATIONS: Mapping[key, implementation]`, keyed as in AD-SYM-03 D-b — the resolved `C` context
  (`CContext`) and command constants (removal, Collapse, Cap, Extrude, Loop Insert, Apply transform, mirror copy), with a
  symmetric variant where the symmetric path differs (Knife, F-6). The value is the implementation the app already runs,
  so a rename fails loudly, and a parametrized test runs every declared entry on a layered fixture against its rule in
  §3 / §4.1 — an entry without a rule fixture fails (declaration = tested support).
- `Application` consults the gate only when the mesh has layers, where the operation is resolved — after
  `resolve_c_context` in `_connect_command` (the G-2 position), at the Extrude / Knife arm, per command for removal,
  Collapse, Cap, Apply, mirror copy — before any mutation, and refuses visibly (status names the operation and the
  reason; text `PROVISIONAL`, e.g. `"Knife: locked while this mesh has morph targets"`). No layers: no lookup,
  behaviour unchanged.
- **Fail-closed:** allowed = non-mesh commands (selection, display, modes, Undo/Redo, cancel, constraints, region / mask /
  hide / symmetry commands) ∪ position-only commands ∪ declared operations. An enumeration test classifies every command
  that can reach a mesh mutation; an unclassified one fails (the AD-SYM-03 §2.5 allow-list pattern). Position-only
  commands get a contract test: layers bit-identical afterwards.
- **Core backstop:** `add_vertex` without an origin on a layered mesh raises. The backstop catches a forgotten origin
  (mechanical omission); the gate catches what the Core cannot see — a tool that post-processes positions so the
  primitive's interpolation no longer fits (F-6), a frame change that rewrites positions without the map. External hosts
  (`apply_mesh_change`, labs) get the backstop, not the gate.
- **H1 is the table's content** (§10).

### 4.5 Relation to `face_regions`

Kept as it is: membership is boolean and needs no interpolation, and the inference covers every face-creating operation
today, fail-closed. Later options, each with its trigger: (a) an exact face origin from `split_face` (the parent is known
in the primitive), when Knife interior shapes must inherit (AD-REGIONS-01 §2); (b) a face-domain layer — the same
per-element mechanism on faces — when the whole-value journal (~4 MiB / ~55 ms per change at 87k faces) is measured too
slow. Corner-domain data (UVs) would use the same primitive hook on (face, vertex) corners — not now.

## 5. Alternatives (M1 history)

| # | Alternative | Not used, because |
|---|---|---|
| X-1 | Collect origins afterwards from the journal (the regions pattern) | The journal holds the removed edge's ends but not `t`, and not a tool-built vertex's source (Extrude); recovering them is geometric inference (X-5). Every commit boundary needs a hook with its own nested-rollback bookkeeping — three region hooks already cost one broken import boundary (audit §B, fixed in Phase 0) |
| X-2 | Layers outside the Mesh (Scene, Object, an app store) | Desynchronize on Undo, Knife checkpoints and Extrude cancel unless every boundary mirrors the journal (AD-SYM-01 §1.1, AD-REGIONS-01 §1.2); need a file home of their own; contradict AD-021 §4.9 |
| X-3 | Target as a mesh copy (Morph Lab) | 52 / 207 MiB per target [C, audit]; IDs drift apart at the first topology edit (the Lab switches off); 20–50 targets do not fit 8 GB. The Lab's "beside the base" stays, as an editing view (H4) |
| X-4 | Half-Edge migration | Fixes none of the audit's four limitations (§A, §C); rewrites `mesh.py` and every tool and re-proves ~3,000 tests plus the 351-test Knife oracle; AD-002 keeps the swap possible later |
| X-5 | Geometric inference (midpoint matching, nearest point) | Medium reliability (FINDINGS-3AB), fails for t ≠ 0.5 (AD-017 B1b), ambiguous for coincident midpoints. Stays the tool for transfer between *different* meshes (Phase 7) |
| X-6 | AD-005 listener design (`topology_listeners`, `on_vertex_created(new, parent, context)`) | One parent is wrong for an edge split (a blend); listener-held data lives outside the journal, so `rollback_change` / `revert_change` (Knife checkpoints, nested Collapse) would not restore it; bones on the Mesh contradict AD-021 §4.9; never implemented, superseded |
| X-7 | A stored provenance record (origin per vertex in the Mesh, the journal or History) for later remapping | No consumer needs it once layers interpolate at mutation time; it grows with every edit; ARCH-02: no large remapping framework before real use cases |
| X-8 | Whole-value journaling of layers (like `face_regions`) | A dense 87.5k layer is 16 MiB per change; regions already measure ~4 MiB / ~55 ms per change at 87k faces |
| X-9 | Absolute target storage (a position per point and target) | Every base edit would have to update every target (J-3 asks for the opposite); a new point's interpolated absolute position would not match its exact rest position on a non-planar face — offsets keep the rest point where the artist cut |
| X-10 | Barycentric weights on the face's drawn triangle | Exact for 3D-affine data on the drawn surface, but tied to the viewport's ear clipping (F-12) and the boundary rotation, and only C0 across diagonals: the Core would depend on a display algorithm. MVC's measured error (§4.1) is accepted |
| X-11 | Interpolation only in Phase 5 (audit §G) | A primitive must define its layer behaviour from the first day a layer exists (write something or refuse); one CORE_V1_FREEZE §7 exception and one oracle cover interpolation and Undo together; the product exposure stays staged by the gate |
| X-12 | Gate only, no Core backstop | A tool calling `add_vertex` without an origin would silently store zero offsets (dents) — the "never silently wrong" intent of ANIMATION.md item 5 |
| X-13 | Core backstop only, no gate | Cannot see semantic misuse (F-6, frame changes) |

## 6. Artist-facing consequences (no decision asked)

- Nothing visible changes before Phase 3; Phase 2 is Core plus tests.
- With targets, the base's picking, selection and the tools stay on the rest shape (F-11 "hilft").
- An expression follows later base edits (J-3); a whole-mesh rotate / scale in `1`/`2`/`3` is an edit (§4.3).

## 7. Phasing (refines audit §G)

- **Phase 2 — Core extension and gate.** §4.1–§4.3 in the Core (layers, journal, file, origins in every primitive
  including `collapse_elements`, `add_vertex(origin=…)` with the backstop, `map_vector_layers`), the gate with the H1
  default table, the F-9 consumers. No UI and no target creation in the app; exercised by tests. Needs the review
  disposition and Manu's go for the Core change, **not** the H answers (parameters with defaults).
- **Phase 3 — one persistent target** (audit Phase 3 unchanged). Needs H1 (the table as shipped) and H4. Apply transform's
  `map_vector_layers` call is recommended here (one line in `apply_placement`, F-7).
- **Phase 4** unchanged; the packed-storage decision belongs here.
- **Phase 5 — tool wiring and gate lifts,** one operation at a time with its acceptance test: Split / Edge Connect / Loop
  Insert (only the gate entry — the primitives already interpolate), Knife (with the symmetric replay at the mapped t),
  Extrude (`origin=`), Collapse, mirror copy; the artist test (loops around eyes and mouth with 3 targets). H2 / H3 become
  visible here.
- **Phases 6–7** unchanged; the weights kind is built with Phase 6.

## 8. CORE_V1_FREEZE §7 for the Phase 2 Core extension

1. **Requirement.** Persistent morph targets (ANIMATION.md items 1–3; 20–50 targets, AD-023 header) and topology edits
   after targets as a planned strength that the first version's lock must not block (ANIMATION.md item 5, Manu
   2026-10-20) need per-point data that rides Undo, Knife checkpoints, rollback and the file, and a defined value for
   every point a primitive creates or merges.
2. **Public API?** No: data outside the mesh desynchronizes (X-2); the journal cannot reconstruct origins (X-1, X-5);
   whole-value data on the mesh is too expensive at this size (X-8).
3. **Architecture problem documented:** this AD and the audit.
4. **Smallest extension:** `core/ids.py` — `LayerId`. `core/mesh.py` — `LayerKind`, `PointLayerInfo`, layer storage,
   `_touch_l`, `MeshChange` / `MeshDelta` slots, the layer methods of §4.2, the origin in `add_vertex` (keyword with a
   default), `split_edge`, `split_face`, `collapse_edge`, `_delete_vertex`, the `export_state` / `load_state` keys, the
   apply order. `core/operations/collapse.py` — the group merge. `core/__init__` — exports. **Not touched:** `Operation`,
   `OperationContext`, `HistoryStack`, `MeshDeltaCommand` (it carries the delta unchanged), `MeshStateCommand`, `Scene`,
   `serialization.FORMAT_VERSION`, `Selection`, every existing signature. **Without layers the behaviour is
   byte-identical**; `export_state` gains two additive keys.
5. **Contract tests:** §9.
6. **Then implement**, and record the §7.1 entry with the commit.

## 9. Phase 2 contract tests and acceptance

| # | Test | Guards |
|---|---|---|
| T-1 | Randomized journal sequences with layers (extends `tests/test_mesh_change_journal.py`): a grid with three layers (two sparse vector layers, one with `zero` / `keep` rules), `_random_op` over every primitive plus `add_vertex(origin)` and the layer writes (add / remove / rename / reorder, set incl. the default, `map_vector_layers`); L1–L5 after every step; Undo to the start and Redo to the end against the snapshot oracle (export incl. `"point_layers"`, container orders, every counter forward incl. `layer_id_counter`); the existing 12 seeds × 25 steps plus one long run | exactness contract (1)–(7) |
| T-2 | Nested rollback, `revert_change`, `release_change` with layers (the Knife checkpoint pattern); a watch sees layer-only changes; a layer-only change is a non-empty delta | (5), (6) |
| T-3 | Analytic rule per primitive: `split_edge` values bit-equal to the position expression; `split_face` MVC against an independent reference (≤ 1e-12 relative), affine data on planar convex and concave faces ≤ 1e-12 of the spread, on-corner / on-edge equal to the corner / `split_edge` rule, degenerate parent total; `collapse_edge` and `collapse_elements` for `average` / `keep`; `add_vertex` origin copy bit-exact, weighted origin, `()` → defaults, `None` with layers → `MeshError` with the mesh and counters unchanged; `new_point="zero"`; Delete / Dissolve remove values | §4.1 |
| T-4 | No-layer equivalence: every existing suite unchanged except the assertions that pin the export key set; layer-free random sequences export identically apart from the two keys | byte-identical behaviour |
| T-5 | File: export → JSON → load bit-exact (values, ids, names, order, rules, counter); a file without the keys loads; invalid kind / rule / duplicate name / dead vertex → `ValueError`; `load_state` under a journal records only differing values | §4.2 File |
| T-6 | Knife: `experiments/knife_oracle/tests` green (trigger list: `split_face`, `split_edge`, the journal); plus the resolver on layered copies of the golden sessions — each new vertex's value equals the replayed per-call rule of its kept call, Undo exact | composition (§4.1) |
| T-7 | Gate: the enumeration test; an undeclared operation with layers is refused before any mutation (mesh, history, selection unchanged, status set); the H1 defaults run; position-only commands keep layers bit-identical; without layers no lookup (existing app tests unchanged) | §4.4 |
| T-8 | `map_vector_layers` rule on random matrices; mirror-copy index map (when wired: Phase 5) | §4.3 |
| T-9 | `SessionStart.unchanged()` / `.state()` with layer changes; a layer-only Undo rebuilds no topology | F-9 |
| T-10 | Mutation checks by hand, as in AD-023 §9: a write path without `_touch_l`, a wrong apply order, no value deletion in `_delete_vertex`, `split_edge` with swapped weights — each must fail a test | the tests themselves |

**Measured and recorded** [C], gollum_20k and gollum (87.5k): memory per layer at 15 % / 100 %; `set_layer_value` with one
and five logs; `split_edge`, `split_face`, `collapse_edge`, `delete_vertices(1000)` with 0 / 10 / 50 layers; one dense
layer rewrite under one recording; `export_state` + `load_state` with 50 sparse layers. **Acceptance:** within 1.5× of
this AD's prototype numbers (§4) or explained. No reference-PC run is needed for Phase 2 (no UI).
**Runs** (AGENTS.md §8a, `src/core` change): `pytest tests -q`; GL tests in their own process; `experiments/morph_lab/tests`;
`experiments/knife_oracle/tests`. **Done:** all green, the CORE_V1_FREEZE §7.1 entry, an implementation note here with the
measured numbers, status → IMPLEMENTED (Phase 2).

## 10. Artist decisions H1–H5 as parameters

| | Decides | Lives in | `PROVISIONAL` default (audit §H) | Needed by |
|---|---|---|---|---|
| H1 | Which operations run while a mesh has targets | the gate table's entries (§4.4) | allowed: Delete, Dissolve, Vertex Connect, Cap, every position-only tool; locked with a message: Split, Edge Connect, Loop Insert, Knife, Extrude, Collapse (and Apply transform / mirror copy until wired), lifted one by one in Phase 5 | Phase 3 |
| H2 | What a new point does in an existing target | `PointLayerInfo.new_point` | `"interpolate"` (follows its neighbours linearly; a touch-up may be needed in strongly bent areas) | Phase 5 (visible) |
| H3 | What merged points keep | `PointLayerInfo.merge` | `"average"` (matches the merge-at-centre position) | Phase 5 (visible) |
| H4 | How a target is edited | the Phase 3 editing view; no Core impact (both answers write the same layer values) | beside the base (J-5), shape edits on the view, topology only on the base | Phase 3 |
| H5 | Scope and order | the phase plan | yes to: fluid on head / body and "usable" on 20k until the GPU phase; topology-after-morphs (Phase 5) before skinning (Phase 6); morph + SubD together from Phase 4 | Phase 3 |

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
- Face- and corner-domain layers; packed storage (Phase 4); a whole-layer replacement record (§4.3).

## 12. Risks and their guards

| Risk | Guard |
|---|---|
| A write path misses `_touch_l` → Undo leaves a stale value | T-1 oracle, T-10 mutation check |
| A tool adds vertices without origin | Core backstop (raises), T-3 |
| A tool post-processes positions after a primitive (F-6) | gate entry only with its rule test (T-7), Phase 5 fix |
| MVC on strongly warped faces visibly off | measured (§4.1, p99 0.09 mm per 5 mm); H2 touch-up note; Phase 5 artist test |
| Journal cost grows with active watches (up to six logs, F-10; measured up to five) | measured (§4.2); per-watch opt-out of layer records is the follow-up if Phase 3 measures it |
| File grows with dense targets | sparse canonical storage (L2); packed storage in Phase 4 |
| Readers of `MeshChange` internals miss layers | T-9; grep for `MeshChange` slot readers in Phase 2 |

## 13. Review request (Erzeuger ≠ Bewerter)

**For:** a fresh session, not this one (AGENTS.md §6, Development System §6). **Suggested:** Claude Opus 5.5, reasoning
effort `xhigh` (Core-freeze territory, numerical claims, many code paths). Archive the first-pass review unedited, e.g.
as `docs/archive/deformation/reviews/AD-025_REVIEW_CLAUDE_001.md`, before any discussion; the author records the
disposition of each finding here.

**Must check:**

1. §1 F-1…F-12 and every row of §3 against the code at `a53c14f` (and any later `src/` change): IDs kept / created /
   invalidated, the commit boundary of each operation, the symmetric paths.
2. That every vertex creation and deletion in `src/` goes through the paths named in F-2 / F-3 — anything else is a hole
   in §4.1.
3. §4.2 against AD-023 §2 H1 point by point, especially the apply order of meta and values, `revert_change` on a
   checkpoint, and `load_state` under a journal.
4. The measurements: re-run small versions of the probes (journal cost per write with 1 and 5 logs, memory per layer,
   MVC accuracy on warped quads and on real gollum_20k faces, nested vs. direct) and say whether the numbers hold.
5. That the H1 default and the gate's fail-closed classification cover every command in `commands.py` that can reach a
   mesh mutation.
6. That §8 is the smallest Core extension and §9 would catch a wrong implementation.

**Questions to challenge:**

- Is moving the primitive interpolation into Phase 2 (X-11) right, or does it widen the Core change before a target
  exists?
- MVC in the Newell plane vs. barycentric on the drawn triangle (X-10): is the measured error on warped faces acceptable,
  and is the per-call composition rule (closed Knife shapes) acceptable?
- Should `add_vertex` without an origin raise on a layered mesh, or store defaults?
- Are per-layer `new_point` / `merge` rules (H2 / H3 as data) the right home, or should they be one mesh-wide setting?
- Is the edit vs. frame-change rule (§4.3) what an artist expects for a whole-mesh rotate or scale in component mode?
- Is a symmetric variant key in the gate (Knife) enough, or must every symmetric coordinator be declared separately?
- Does any consumer of `MeshChange` / `MeshDelta` misbehave on a layer-only change (pick cache, render mesh, SubD
  preview, soft shading, the selection mirror in `_apply_undo_redo`)?
- Does the additive `"layer_id_counter"` key at the top level break a test or a reader that iterates the state keys?

---

## Kurzfassung für Manu (Deutsch)

**Worum es geht:** Damit Morph-Ziele später Topologie-Änderungen überleben, speichert das Mesh pro Ziel nur, wie weit jeder
Punkt von der Basis abweicht (statt einer ganzen Mesh-Kopie — passt zu deiner Antwort J-3 „relativ“). Jedes Werkzeug, das
einen Punkt erzeugt oder zusammenführt, gibt ihm im selben Moment seinen Wert; Undo, Abbrechen und Speichern laufen wie bei
den Positionen. Vor dem Bau prüft eine unabhängige Review diesen Entwurf; sichtbar ändert sich für dich erst mit dem ersten
Ziel in der App.

**Deine fünf Entscheidungen** (je eine Zeile; „ja“ = Empfehlung):

- **H1** Solange ein Mesh Ziele hat: Löschen, Auflösen, Vertex Connect, Cap und alle Verschiebe-/Glätt-Werkzeuge erlaubt;
  Split, Connect Edges, Loop Insert, Knife, Extrude und Collapse mit Meldung gesperrt, bis sie einzeln freigegeben werden?
  — *ja / alles sperren / alles sofort*
- **H2** Ein neuer Punkt (z. B. Loop Insert) bewegt sich im Ziel mit seinen Nachbarn mit (wie Blender; in stark gebogenen
  Stellen evtl. kurz nachformen) — oder bleibt er unbewegt (Delle)? — *ja / unbewegt*
- **H3** Beim Zusammenführen (Collapse) bekommt der übrige Punkt den Mittelwert der Ziel-Bewegungen — oder die eines der
  Punkte (kann an Ausdrucksspitzen leicht reißen)? — *ja / einer*
- **H4** Ein Ziel bearbeitest du weiter daneben wie im Morph Lab (Form am Ziel, Topologie nur an der Basis) — oder an Ort
  und Stelle mit Ziel-Umschalter (Blender-Art)? — *ja / an Ort und Stelle*
- **H5** Reihenfolge: ein Ziel → mehrere → Topologie-Änderungen mit Zielen → Rig; Morph + SubD zusammen ab mehreren Zielen;
  flüssig auf Kopf und Körper, auf gollum_20k vorerst „benutzbar“? — *ja / andere Reihenfolge*

**Zur Kenntnis (keine Frage):** Drehst oder skalierst du das ganze Mesh in `1`/`2`/`3`, bleiben die Ziel-Bewegungen, wie sie
waren. Einen Charakter mit Zielen skalierst du in `4` und übernimmst den Transform (`Strg+A`) — das nimmt die Ziele mit.
