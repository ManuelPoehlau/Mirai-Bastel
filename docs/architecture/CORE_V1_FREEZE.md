# Mirai-Bastel Core V1 — Produktions-Freeze

**Status:** FROZEN (with authorized exceptions; see §7.1)
**Datum:** 2026-08-27
**Revidiert:** 2026-10-24 (object material: `ObjectMaterial`, `SceneObject.material`, format version 4); previously 2026-10-23 (object mirror pairs: `MirrorPair`, `Scene.mirror_pairs`, format version 3); previously 2026-10-21 (AD-023 §9: Mesh change journal, `MeshDeltaCommand`, vertex → edge index); previously 2026-10-15 (AD-021 M0: Scene objects, `ObjectId`, `Selection.objects`, format version 2); previously 2026-10-14 (AD-SYM-05 SS1: weighted transforms in the Core loop, `params["influence"]`); previously 2026-10-06 (WP Delete/Dissolve: `Mesh.dissolve_vertex/dissolve_edges/dissolve_faces` and `delete_vertices/delete_edges/delete_faces` added); previously 2026-10-01 (AD-017 K1 `Mesh.split_face` extension added, WP-KNIFE-00); previously 2026-09-24 (AD-SYM-02 symmetric Move extension added, WP-SYM-01 Slice 2); previously 2026-09-24 (AD-SYM-01 SymmetryDefinition extension added); previously 2026-09-22 (AD-017 split_edge(t) extension added); previously 2026-09-17 (AP-05 `add_edge()` precedent added; previously 2026-09-04, ADR-001 precedent added)
**Grundlage:** Hardening-Phasen A–E + Gesamtarchitektur-Review

## 1. Entscheidung

`src/core/` wird nach Abschluss des Hardening- und Architektur-Reviews als **Core V1 eingefroren**.

Freeze bedeutet nicht, dass der Core niemals wieder geändert werden darf. Es bedeutet:

> Eine Änderung an `src/core/` benötigt ab jetzt eine konkrete neue Anforderung, die zeigt, dass der bestehende V1-Vertrag nicht ausreicht.

Zukünftige Systeme werden nicht vorsorglich in den Core eingebaut.

### §7.1 Authorized Exceptions (Precedent)

**Decision:** ADR-001 (2026-09-04, ACCEPTED)

Transform operations (`RotateOperation`, `ScaleOperation`) are promoted from experiments to `src/core/operations/transform.py` as authorized production extensions.

**Rationale:** These operations are fundamental modeling operations, not speculative future systems. They are production-grade (per Gate 2 classification) and belong in Core as first-class citizenship.

**Process for future exceptions:** Follow same analysis as ADR-001 (classify operation, justify promotion, document precedent).

**Decision:** AP-05 (2026-09-14, commit `50fbee8`)

`Mesh.add_edge()` is promoted from the topology experiment (Connect Edges' "kind v" / FreeConnect
case) to `src/core/mesh.py` as an authorized production extension — a minimal, public mutation
primitive for a free edge between two vertices without a shared face. Covered by an
architecture-contract test including error cases and invariants (`tests/test_core.py:128-165`).
Follows exactly the flow this document's own §7 (below) and `docs/architecture/ROADMAP.md §13`
describe: experiment demonstrated the need (Connect Edges' "kind v" case), finding documented, Core
extended, existing methods (`split_edge`/`connect_vertices`) left unchanged.

**Decision:** AD-017 (2026-09-22)

`Mesh.split_edge(edge_id, t=0.5)` is extended with an optional `t` parameter (default 0.5,
bit-identical to the existing midpoint behaviour). Rationale: Knife mode makes non-midpoint splits
the normal case; the documented "splits at the midpoint" contract would otherwise misrepresent the
result; the rigging experiment's midpoint-matching fallback (FINDINGS-3C, 3C-2) fails for t ≠ 0.5,
leaving the (edge, t) pair as the reliable provenance path (AD-017 B5/B1b). Backward compatible:
all callers that call `split_edge(eid)` are unaffected. Covered by new contract tests in
`tests/test_core.py`. `Mesh.add_edge()` retained unchanged; no active production consumer after
strip Connect was rejected; retained for potential future construction/curve work (AD-017 §13).

**Decision:** AD-SYM-01 (2026-09-24, WP-SYM-01 Slice 1)

`Mesh` gains a `symmetry_definition: SymmetryDefinition | None` attribute (`src/core/mesh.py`) —
Plane (point + unit normal) and a declared set of Seam `EdgeId`s, default `None` ("symmetry off").
Authorized by `docs/architecture/AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md` (DECIDED): the
Definition is bound to the Mesh's own ID space and must not outlive a Mesh replacement or
desynchronize from an Undo — both already hold for Mesh's own containers, neither holds for a
Scene-level location (measured regression in AD-SYM-01 §1.1). `export_state()`/`load_state()` gain
an additive, optional `"symmetry"` key (no `FORMAT_VERSION` bump; `state.get("symmetry")` so a dict
without the key still loads); `MeshStateCommand` therefore carries the Definition through Undo/Redo
without any new History machinery (AD-SYM-02 §5). Mesh stores this declaration only — it does not
interpret it; Correspondence-Ableitung and State-Aggregation live in `src/mirai/symmetry.py`
(outside the frozen Core, same placement rationale as `scene_factory.py`/`mesh_geometry.py`,
AD-008). Covered by `tests/test_symmetry.py` (storage/roundtrip, the AD-SYM-01 §1.1 regression case,
all four Correspondence states, all Symmetry State outcomes) and a roundtrip regression added to
`tests/test_scene_serialization.py`. No operation, tool, or Undo/Redo *behavior* for the Definition
itself in this slice (Definition is set directly, e.g. `mesh.symmetry_definition = ...`) — that is
explicitly out of scope for WP-SYM-01 Slice 1.

**Decision:** AD-SYM-02 (2026-09-24, WP-SYM-01 Slice 2)

`Operation` (`src/core/operation.py`) gains `supports_symmetry: bool = False`, a class attribute
following the same precedent as `description` — an Operation-level statement, not touching the
lifecycle, abstractly queryable before any `begin()` and even without an instance. `MoveOperation`
overrides it to `True`; `RotateOperation`/`ScaleOperation` keep the default `False` (symmetric
Rotate/Scale is explicitly out of scope for this slice). Authorized by
`docs/architecture/AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md` (DECIDED) §2.3.

`VertexTransformOperation._on_update()` (`src/core/operations/transform.py`) additionally passes
`vertex_id=vid` into `_transform_position()` — the one minimal extension of the shared Move/
Rotate/Scale loop needed for per-vertex differentiation (analogous to the existing `self._weights`
soft-selection placeholder). `RotateOperation`/`ScaleOperation` are unaffected (both already accept
arbitrary kwargs via `**_`); only `MoveOperation` (`src/core/operations/move.py`) uses it, to apply
one of three vertex-category deltas per AD-SYM-02 §2.4: directly selected vertices get the plain
`delta`; mirrored partner vertices (inferred via `mirai.symmetry.vertex_correspondence()`, resolved
by `MoveTool` before `begin()`, never a vertex already part of the Artist's explicit selection — see
`core/operations/move.py` module docstring for the full edge-case rationale) get the delta *vector*
reflected across `plane_normal` (`d' = d - 2*(d·n)*n`); Seam vertices among the selected get the
delta projected onto the plane (`d_proj = d - (d·n)*n`, INV-2). The symmetry context travels through
the existing, unmodified `OperationContext.params["symmetry"]` (same channel `pivot` already uses,
AD-SYM-02 §2.2) — no new field on `OperationContext`, no `MirrorResult` structure, no History
extension: one symmetric Move is still exactly one `Operation` instance and exactly one History
entry (AD-SYM-02 §2.1, already guaranteed by the existing `Operation.commit()` contract). Covered by
`tests/test_symmetric_move.py` (mirrored-delta math, the mirror invariant held after the move,
multi-update incrementality, single History entry + Undo/Redo across both sides, Cancel restoring
both sides exactly, Seam projection staying exactly on the plane, the unaffected no-symmetry
regression case, the explicit-both-sides-selected edge case, and the `supports_symmetry` flag) plus
`SymmetricMoveIntegrationTests` in `tests/test_tool_integration.py` (same behavior through the real
`MoveTool`/`Application` pipeline, not just the Operation layer). `mirai.symmetry` additionally gains
`mirrored_selection()` (pure function, no cache, AR-1) — covered by `TestMirroredSelection` in
`tests/test_symmetry.py`.

**Decision:** AD-017 K1 (2026-10-01, WP-KNIFE-00)

`Mesh.split_face(face_id, v_a, v_b, positions=())` is added to `src/core/mesh.py` as an authorized production
extension — one additive primitive that splits a face along a path `v_a → positions… → v_b` (the B2c sketch of
`docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md` §3). Rationale: the Artist KEEP'd the Q5 face constructions
(notch, closed shape, loop at a point) and chose K1 for the One Knife (Manu, 2026-10-01); the public API can build
them only by face surgery in the tool (`remove_face` + `add_vertex` + `add_face`), which contradicts AD-017 B5 and
the V1_SPEC mutation-layer principle; a primitive that knows the parent face, the path and both sides is also the
natural provenance hook (ARCH-02). With `positions == ()` it is bit-identical to `connect_vertices` (one documented
refusal more: a chord that is already an edge of another face). The accepted contract and the freeze-rule table are
in `docs/architecture/AD-017_FINAL_DECISIONS_2026-09-22.md`, Addendum 2026-10-01. Covered by the `test_split_face_*`
contract tests in `tests/test_core.py` (ID continuity, `connect_vertices` twin, notch, unchanged mesh incl. allocator
counters on every error, winding, both argument orders, serialization and `MeshStateCommand` Undo/Redo round trips,
symmetry definition untouched) and by `experiments/knife_oracle/tests/test_split_face_equivalence.py` (same faces as the Lab
stand-ins on grid, cube and head). `connect_vertices` and `split_edge` unchanged; no new `Operation`, no
serialization change.

**Decision:** AD-SYM-02 §2.4 follow-up (2026-10-03, WP-SYM-LAB-02 S2)

`RotateOperation`/`ScaleOperation` (`src/core/operations/transform.py`) become symmetric the same way
`MoveOperation` did, and flip `supports_symmetry` to `True` (both inherit it from a new private
intermediate class `_PivotTransformOperation(VertexTransformOperation)`; `Move`, `Operation`,
`OperationContext` and History are untouched). The symmetry context travels through the existing
`OperationContext.params["symmetry"]` (`plane_normal`, `mirrored_vertex_ids`, `seam_vertex_ids`, plus
`plane_point` — a pivot is a *position* and can only be mirrored with a plane point). Three vertex
categories, one interaction, one History entry: directly selected vertices get the ordinary transform
about the pivot; mirrored partners get the *conjugated intent* — rotation about mirror(pivot) around
mirror(axis) by −angle, scale about mirror(pivot) with factor b_i applied along mirror(b_i) (a
reflection reverses handedness), computed as `mirror(T(mirror(p)))` so the partner is the *bit-exact*
mirror of the source position (`mirai.symmetry` finds partners by exact position equality, AR-1; an
approximation would silently degrade a pair to UNPAIRED); Seam vertices get the ordinary transform,
projected exactly onto the plane afterwards. The Operation hard-codes no centroid: the pivot is
`params["pivot"]` (mirrored for partners) or, as before, the centroid of the affected vertices;
`RotateTool`/`ScaleTool` (shared `TransformTool._on_begin`, helper `resolve_symmetry()` in
`selection_helpers.py`, same resolution as `MoveTool.begin()`) pass the affected set (selection ∪
partners; an explicitly selected partner wins and the pair then moves as a rigid group) and, when no
pivot is given under symmetry, the centroid over selection ∪ partners (a single vertex turns about the
pair midpoint). *Superseded 2026-10-03 (Artist decision, WP-SYM-LAB-03 joint session, `src/mirai`
only, no Core change):* the default is now the centroid of the explicit selection, per side, mirrored
for the partners by the operation; fallback to selection ∪ partners when a seam vertex is affected and
the own centroid is off the plane (`selection_helpers.symmetric_default_pivot`). Seam contract (INV-2/INV-8): a Seam vertex stays on the plane only if the pivot is on
the plane AND rotation axis ∥ plane normal / scale is uniform or normal-aligned (normal is an
eigenvector of the scale matrix); otherwise the tool refuses *before the first motion* with the new
`SeamConstraintError` (the Operation raises the same error as a backstop, before touching any vertex).
Agent assumption: "on the plane / parallel" is decided with an absolute tolerance
`SEAM_TOLERANCE = 1e-9`, inside which the Seam result is projected exactly onto the plane (centroids
carry ~1e-17 rounding residue; the existing VIOLATED check is exact). Production behaviour is
unchanged: no symmetry can be switched on in the Production app, so `params` carries no `"symmetry"`
key and the maths is the previous code path (asserted in `tests/test_symmetric_transform.py`).
Covered by `tests/test_symmetric_transform.py` (bit-exact mirror equivalence over random axes/angles/
factors and 60 incremental updates with pivot on and off plane, oblique-plane tolerance case,
documented-formula equivalence, rotation sense for normal vs. in-plane axis, single vertex, rigid
explicit pair, Seam allow/refuse cases staying exactly on the plane, cancel/commit/Undo) and
`tests/test_symmetric_move.py` (flag flipped). Free pivots and a pivot UI remain out of scope.

**Decision:** WP Delete/Dissolve (2026-10-06, `docs/WP_DELETE_DISSOLVE_PLAN.md`)

Six additive removal primitives are added to `src/core/mesh.py` as an authorized production extension: the
preserving `dissolve_vertex(vertex_id)`, `dissolve_edges(edge_ids, *, cleanup)`, `dissolve_faces(face_ids, *,
cleanup)` and the destructive `delete_vertices(vertex_ids)`, `delete_edges(edge_ids)`, `delete_faces(face_ids)`.
Freeze rule (§7): (1) requirement — Delete/Dissolve on all three element levels in the Production app (Artist
decisions Manu 2026-10-06, plan §0.2); until now collapse was the only removal. (2) Not solvable with the public API:
no public operation removes an edge or a vertex, and merging faces through `remove_face` + `add_face` is the same face
surgery in the tool that AD-017 B5 / K1 ruled out. (3)/(4) Smallest extension: one internal planner
(`_region_outline` / `_plan_dissolve`, read-only, every precondition checked before the first mutation — on
`MeshError` the mesh incl. allocator counters is unchanged) and one apply step shared by all three dissolves; one
internal delete core shared by the three deletes. Decisions made while building (plan Status: "beim Bauen
entschieden"): `cleanup` is keyword-only without a default (the variant is a binding choice, §0.2.2, and part of the
public signature, never silent); the plan's `dissolve_edge(edge_id, cleanup)` became `dissolve_edges(edge_ids, *,
cleanup)` — atomic over a selection, because with per-edge cleanup the first edge can remove the endpoint the next
selected edge hangs on (two edges at a cube corner); for one edge it is the plan's operation. Vertex and Edge Delete
got own primitives (no public edge removal exists); Delete removes the given elements, their faces, every edge of
those faces that is left without a face (inner edges and former mesh-border edges alike) and vertices left without an
edge; edges still used by a remaining face stay as the hole border (plan §0.2.3 as clarified by Manu 2026-10-06: "a
floating edge goes"). `remove_face` keeps its V1 contract (edges stay). A dissolve that merges faces creates one new `FaceId`
per region (all region `FaceId`s become invalid); removing a 2-valent vertex creates one new `EdgeId` per chain and
keeps the neighbour face's `FaceId` (its boundary loses the vertex) — the exact inverse of `split_edge` up to the new
id. Each method documents its ID continuity in the docstring. `collapse_edge`, `remove_face` and every existing
method unchanged; the Symmetry Definition is not touched (symmetry behaviour is out of scope); no new `Operation`, no
serialization change; Undo/Redo through the existing `MeshStateCommand`. Covered by
`tests/test_core_delete_dissolve.py` (43: ID continuity, no-op, error with unchanged state incl. counters, the
2×2-grid cases (corner face, two faces), cube both variants, 3×3 loop to pure quads, shared chain, degenerate/existing-edge skips, hole and
self-touching regions, bowtie, winding, MeshStateCommand Undo/Redo + serialization round trip, symmetry definition
untouched) and `tests/test_application_delete_dissolve.py` (Production path).

**Note (docs only, no Core change):** *Superseded 2026-10-14 by the AD-SYM-05 entry below (the weighting moved into the
Core, the soft ops became thin subclasses of the Core ops, the F3 tripwires flipped); kept as the record.* WP-SOFT-01 S2a (2026-10-10, AD-020 Q2-D, review F3). `src/mirai/soft_selection`
(`SoftMoveOperation`, `SoftRotateOperation`, `SoftScaleOperation`) subclasses `VertexTransformOperation` from
`core.operations.transform` — the first `src/mirai` class that subclasses a Core `Operation`. It uses the protected
template-method hooks `_on_begin` / `_on_update` / `_transform_position` of that unexported class and the public
`pivot`, `vertex_ids` and `rotate_around_axis`; **no Core private member and no private helper**. What it relies on is
pinned by tripwire tests in `tests/test_soft_selection_ops.py` (AD-020 §13 F3), so a later Core edit — e.g. filling the
inert `_weights` soft-selection placeholder — fails loudly instead of silently double-weighting. This is "solvable
without a Core change" (§1), not "with the public API" (§7 step 2). Whether the weighting moves into the Core is the
promotion decision of AD-020 §12/§13 F4, after the S2c verdict.

**Decision:** AD-SYM-05 (2026-10-14, AD-SYM-04 slice SS1; Manu's go 2026-10-14 after review CLAUDE-001)

`VertexTransformOperation`, `MoveOperation`, `RotateOperation`, `ScaleOperation` (`src/core/operations/transform.py`,
`move.py`) read **`params["influence"]`**, the soft weights (`VertexId -> w`, `w` in (0, 1], keys exactly the op's vertex
set; `ValueError` otherwise, before anything is stored). Freeze rule (§7): (1) requirement — symmetric Soft Selection with
P-a (AD-SYM-04 Q-4, M-5 "Core opened once"); (2) not solvable without a Core change: the mirror logic of the transform
family and both seam checks live in the Core (AD-SYM-02 §1 "genau eine Stelle"), soft ops outside it would need a second
copy; (3) documented in AD-SYM-04 §4 and [AD-SYM-05](AD-SYM-05-WEIGHTED-TRANSFORMS-IN-CORE.md); (4) smallest extension: one
`params` key already in use, one new category key `falloff_seam_vertex_ids` inside the existing `params["symmetry"]`, the
inert placeholder blend `pos + w·(T(pos) − pos)` deleted, accumulated totals only where an absolute path needs them, **no
new public API** (`Mesh`, `Operation` lifecycle, `OperationContext`, History, `VertexTransformCommand`, topology untouched).
**Without the key every gesture is byte-identical to before** (the old loop; asserted by the existing Core suites and
`tests/test_weighted_transforms.py` T-2). With it each op weights its own parameter (Move `w·Δ`, Rotate `w·θ`, Scale
`1 + w(F − 1)`), then the category applies (plain / conjugate / selected seam / falloff seam); `w == 1` takes the unweighted
arithmetic. Rotate/Scale need `params["pivot"]`; a selected seam vertex must carry `w = 1`. **Documented deviation from
the incremental contract** (`core/operation.py`): Scale evaluates `w < 1` vertices, and Rotate/Scale evaluate falloff seam
vertices, absolutely from the `begin()` snapshot; a weighted Scale fixes the basis for the gesture, a weighted Rotate with
falloff seam vertices fixes the axis and refuses a non-finite angle — without weights nothing is accumulated or fixed. P-a:
falloff seam vertices slide in the plane and are exempt from both seam checks, which keep their scope (`seam_vertex_ids`).
Pair consistency (one weight per pair, opposite categories) is a caller precondition; the Core derives no correspondence.
`src/mirai/soft_selection/ops.py` migrated in the same commit (thin subclasses, M-b: label, symmetry backstop until SS2,
stale-ID filter, `weights`; no arithmetic); `scale_formula`/`"power"` left `src`. No visible behaviour change: the app still
refuses Soft + symmetry (AD-SYM-04 I-8) until SS2. Covered by `tests/test_weighted_transforms.py` (T-2, T-5–T-8 incl. the R-6
straddling fixtures), `tests/test_soft_selection_replay.py` (T-3: non-symmetric Soft bit-identical to Q2-D via a pure replay
function), the ported `tests/test_soft_selection_ops.py` (T-4, flipped tripwires) and the Mehlsack/S1 suites (T-9).

**Decision:** AD-021 M0 (2026-10-15, ARCH-01; Manu's go for M0 2026-10-15 after review CLAUDE-001)

The Scene holds objects. Freeze rule (§7): (1) requirement — a second object in the scene with a Reference state, later
per-object transform/pivot and multi-object editing (Artist decisions A-1…A-5); (2) solvable short-term in the App only
(A′), rejected because it builds a second scene model that the first save or multi-object editing must replace; (3)
documented in [AD-021](AD-021-OBJECT-COMPONENT-MODEL.md); (4) smallest extension per its §5.1–§5.3; (6) Manu's go.
`src/core/ids.py` gains `ObjectId` (an `ElementId` subclass so it reuses `IdAllocator`, AD-021 E-3; same contract:
monotonic, never reused, serialized with its counter). `src/core/scene.py` gains `SceneObject` (`id`, `name`, `mesh`,
`transform`, `pivot`, `state`), `ObjectState` (`NORMAL`/`REFERENCE`) and `ObjectTransform` (translation, rotation as a
3×3 matrix, one uniform `scale > 0`; only similarities are representable — Q-4; the rotation representation is the
agent's choice for E-1, `PROVISIONAL`, `ROTATION_TOLERANCE = 1e-9`); `Scene.objects` is a read-only view ordered by ID,
changed only through `add_object` / `remove_object` (returns the instance; the edit object is refused) /
`restore_object` (re-inserts the same instance and ID, only an ID this scene allocated); `Scene.edit_object_id` lives on
the Scene, validated, persisted (review R-3); `Scene.from_objects(...)` for loading. `Scene()` still starts with one
empty, editable object that is the edit object. **`Scene.mesh` becomes a compatibility property:** get = the edit
object's Mesh (fails loudly if it is missing), set = swap the edit object's Mesh, keeping ID, name, transform, pivot and
state (AD-SYM-01's swap semantics unchanged); today's assignment sites mean "load a new scene", which coincides with
one object (review R-4; M1 routes the app's scene load through an explicit scene reset). `src/core/selection.py` gains
`objects: set[ObjectId]` and `clear_objects()`; `_active_set()` maps `OBJECT` to `objects` (mode `4` was a silent
no-op); **`clear()` and `is_empty()` stay component-only** (review R-2). `src/core/serialization.py` writes format
**version 2** (`object_id_counter`, `edit_object`, `objects[]` with the unchanged `Mesh.export_state()` under `"mesh"`)
and still reads version 1 as one Normal identity object that is the edit object — the first migration, one read branch,
no engine (review R-15; V1_SPEC §12 and the module docstring updated in the same commit). Not touched: `Mesh`,
`Operation`, `OperationContext`, `HistoryStack`, `MeshStateCommand`, `VertexTransformCommand`, every operation; no app
behaviour (M1). Existing tests unchanged except the two that asserted a top-level `"mesh"` key
(`test_scene_serialization.py::…::test_reserved_subsystem_slots_present_and_null_in_v1`,
`test_core.py::test_ad001_serialization_roundtrip`). Covered by `tests/test_scene_objects.py` (default scene, `ObjectId`
never reused and typed, add/remove/restore keeps instance and order, edit object cannot be removed, accessor follows the
edit object, Mesh swap keeps state and placement, transform validation, `Selection.objects` with `clear()`/`is_empty()`
unchanged, P-1 as a Core test — one stack, two objects —, v2 round trip incl. dead IDs, v1 load, inconsistent v2 refused).

**Decision:** AD-023 §9 (2026-10-21; Manu 2026-10-21: "core freeze bedeutet nicht, dass er nicht verändert werden
darf. Bringen uns Veränderungen am Core einen deutlichen Gewinn, sind Core-Änderungen ein Muss.")

`Mesh` gains a **change journal**: `begin_change` / `end_change` (→ `MeshDelta`) / `rollback_change` / `revert_change` /
`release_change` / `apply_delta` / `watch` (`MeshWatch`), and `core.operations.MeshDeltaCommand` / `record_mesh_change`.
Freeze rule (§7): (1) requirement — a topology op and its Undo on 20k took 1-2 s (AD-023 §1); (2) not solvable outside the
Core without per-op touched-set declarations (AD-023 §4 risk) or whole-mesh snapshots; (3) documented in AD-023 §9;
(4) smallest extension: first-touch `_touch_*` hooks in the existing mutation methods, one apply path, a vertex → edge
index (internal), `symmetry_definition` becomes a property with the same get/set; (5) contract tests
`tests/test_mesh_change_journal.py`. **Public behaviour unchanged**: every query returns what it did (`vertex_edges` in
ascending ID order = the old scan's order under the new ascending-order invariant, which `load_state` now establishes);
`export_state` / `load_state` / `MeshStateCommand` unchanged in result. Whole existing Core suite green.

**Decision:** Object mirror pairs (2026-10-23; Manu's go for the recommended architecture of
[OBJECT_MIRROR_SYMMETRY_PROPOSAL](../research/symmetry/OBJECT_MIRROR_SYMMETRY_PROPOSAL.md), the M0 precedent above)

Freeze rule (§7): (1) requirement — two independent mesh objects (left/right eye) whose placements stay mirror images across a
world plane, persistent through Undo/Redo and save/load (proposal §1); (2) not solvable with the existing public API without
storing the relationship twice or outside the scene file (proposal §5.1, §9 decision 1); (3) documented in the proposal;
(4) smallest extension, **data only** like M0: `src/core/scene.py` gains `MirrorPair` (frozen: `a`, `b` ObjectIds, unit
`normal`, `offset`; `a != b` and a unit normal enforced) and on `Scene` `mirror_pairs` (tuple, read-only), `mirror_pair_of`,
`add_mirror_pair` (both objects exist, each object in at most one pair), `remove_mirror_pair`, a `mirror_pairs=` argument of
`from_objects`; `remove_object` refuses a paired object (a pair never points at a missing object — the app breaks the pair
first in the same Undo step). `src/core/serialization.py` writes **version 3** (`"mirror_pairs"` next to the reserved places)
and reads version 2 as version 3 without pairs; an invalid pair makes the file invalid (`ValueError`). Whether placements are
mirrored is **not** a Core invariant (an out-of-sync pair loads as it is and is reported by the app). The coupling maths,
commands and gesture live in `src/mirai` (`object_mirror.py`, `scene_objects.py`, `Application`). Not touched: `Mesh`,
`Operation`, `HistoryStack`, `ObjectTransform` (negative scale stays impossible). Existing tests unchanged except the three
assertions that pinned the version number 2 (`test_scene_objects.py::TestSerializationV2::test_format_is_version_3_with_objects`
(renamed), `…::test_version_1_dict_loads_as_one_normal_edit_object`, `test_scene_files.py::test_save_then_load_round_trips_…`).
(5) contract tests `tests/test_mirror_pairs.py` (value, invariants, v3 round trip, v2 load, invalid pairs refused, `from_objects`).

**Decision:** Object material (2026-10-24; [AD-024](AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md), reviewed and
approved, Manu: "Material pro Objekt, mit der Szene gespeichert"; the mirror-pairs precedent above)

Freeze rule (§7): (1) requirement — every object carries base colour, specular and glossiness through Undo/Redo, save/load,
delete/undo and the scene reset (AD-024 §1); (2) not solvable with the public API: `SceneObject` has `__slots__`, and a
side table keyed by `ObjectId` would store object data outside the scene file format and need a remap on every load
(AD-024 §1.2); (3) documented in AD-024; (4) smallest extension, **data only**: `src/core/scene.py` gains `ObjectMaterial`
(frozen: `base_color` RGB, `specular`, `glossiness`, each finite in [0, 1], invalid values refused with `ValueError`) and
`SceneObject.material: ObjectMaterial | None = None` (one slot, one keyword argument; `None` = the app's default look —
the Core holds no default numbers). `src/core/serialization.py` writes **version 4** (`"material"` per object, `null` or
the three values) and reads versions 2 and 3 as version 4 without material; an invalid material makes the file invalid.
Exported from `core`. The meaning of the values (gloss exponent, fill highlight, selection tint, Reference look), the
Undo command (`ObjectMaterialCommand`) and the setters live in `src/mirai` / `src/viewport`. Not touched: `Mesh`,
`Operation`, `HistoryStack`, `ObjectTransform`, `Selection`. Existing tests unchanged except the three assertions that
pinned the version number 3 (`test_scene_objects.py::TestSerializationV2::test_format_is_version_4_with_objects`
(renamed), `test_scene_files.py::test_save_then_load_round_trips_…`, `test_mirror_pairs.py::test_file_roundtrip_keeps_pairs_and_ids`
(renamed)). (5) contract tests `tests/test_object_material.py` (value, validation, default None, v4 round trip, v2/v3
load, missing key, invalid material refused).

**Decision:** WP Toolbox Gaps B1 Collapse V/E/F (2026-10-23; promotion by Manu,
[WP_TOOLBOX_GAPS_PLAN](../WP_TOOLBOX_GAPS_PLAN.md) B1)

`src/core/operations/collapse.py` gains `collapse_groups` / `collapse_elements` / `CollapseRefused` (a `MeshError`):
each connected group of the given edges falls into one point at its centroid, as a chain of the existing
`Mesh.collapse_edge` plus one `set_vertex_position`. Freeze rule (§7): (1) requirement — Collapse of vertex, edge and
face selections in Production (the command existed but was dead); (2) solvable with the public API, so **`Mesh` is not
touched** — the module only composes `collapse_edge`, the queries and the journal (a nested `begin_change` /
`rollback_change` undoes a half-merged group); (3) documented in the plan; (4) smallest extension: one module next to
`topology.py`, exported from `core.operations`; refusals happen before the first mutation (a face that would hold a vertex
twice, two faces that would coincide, an edge on more than two faces — `tests/mesh_invariants.py` forbids all three);
(5) contract tests `tests/test_core_collapse.py` (edge, edge chain, face group, quad strip, border edge, triangle
degeneration, cube face, the three refusals, 40 randomised selections on sphere / cube / grid: valid with exact
Undo/Redo or refused untouched).

**Decision:** WP Toolbox Gaps C2 Smooth / Relax (2026-10-23; same promotion)

`src/core/operations/smooth.py` gains `smooth_positions` / `SMOOTH_FACTOR`: a **pure function on positions** (Laplace
step toward the neighbour mean, Relax = the step projected onto the vertex's tangent plane, continuous `amount`).
Freeze rule (§7): (1) requirement — Smooth and Relax in Production (MODELING.md priority 1); (2)/(4) no `Mesh` change at
all — the function reads mappings and returns positions, the caller writes them through `set_vertex_position` inside its
own journal; (3) documented in the plan; (5) tests `tests/test_smooth.py`.

**Decision:** AD-REGIONS-01 Face Regions (2026-10-25; [AD-REGIONS-01](AD-REGIONS-01-FACE-REGIONS-STORAGE.md), Manu)

`Mesh` gains `face_regions: FaceRegions | None` (new frozen value types `FaceRegion`, `FaceRegions` in
`src/core/mesh.py`, exported from `core`): named, possibly overlapping sets of `FaceId`s, owned and journaled like
`symmetry_definition` (`MeshChange.regions`, `MeshDelta.regions`; `end_change` / `rollback_change` / `revert_change` /
`apply_delta`), saved as the additive key `"face_regions"` (no `FORMAT_VERSION` bump). Freeze rule (§7): (1) requirement —
saved regions / polygroups for the Character workflow (MODELING.md priority 1) need Undo, Knife-checkpoint rollback and
the scene file, which a Scene- or Application-level store cannot give (AD-SYM-01 §1.1, AD-021 §4.9); (2) additive only,
no existing method or record changed; the Core knows no region semantics and no provenance; (3) AD-REGIONS-01; (4)
`tests/test_mesh_change_journal.py` (random sequences with a `regions` mutation, delta, nested rollback, watch),
`tests/test_scene_serialization.py` (round trip, file without the key); (5) `knife_resolve.SessionStart.unchanged()` reads the
new journal slot.

**Decision:** AD-025 Phase 2 point layers (2026-10-27; [AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) §8,
review CLAUDE-001 dispositioned, Manu's go for the Core change)

`Mesh` owns **point layers**: per-vertex data keyed by `VertexId` (a morph target = one vector layer of offsets). New in
the Core: `LayerId` (`core/ids.py`); `LayerKind`, `PointLayerInfo` (name, kind, new-point rule H2), the layer API
(`point_layer_ids`, `point_layer_info`, `layer_value`, `layer_items`, `has_point_layers`, `add_point_layer`,
`remove_point_layer`, `set_point_layer_info`, `set_point_layer_order`, `set_layer_value`, `map_vector_layers`) and
`add_vertex(position, origin=None)` (`core/mesh.py`, exported from `core`). Origins are **applied, not stored**: `split_edge`
blends (1 − t, t) in the position's own expression, `collapse_edge` averages, `collapse_elements` gives the survivor the
group mean of the original values (`core/operations/collapse.py`), `add_vertex` combines a caller's origin and refuses
`None` on a layered mesh, `split_face` refuses interior points on a layered mesh (both before the first mutation: the Core
backstop), `_delete_vertex` deletes the values. Journal: `MeshChange` / `MeshDelta` gain layer slots in two record shapes —
per element, and one whole-layer record for bulk operations (`map_vector_layers`, `remove_point_layer`, a layer created or
dropped by `load_state`) with copy-on-write of shared value dicts; a `MeshWatch` records layer keys, never values. File:
additive keys `"layer_id_counter"` and `"point_layers"` in `export_state()`, validated whole before the first write;
`serialization.py` writes **version 5** only when a mesh has layers (else 4) and reads 2–5. Freeze rule (§7): (1)
requirement — persistent morph targets that ride Undo, Knife checkpoints, rollback and the file (AD-025 §8.1); (2) not
solvable outside the Mesh (AD-025 X-1, X-2, X-8); (3) AD-025 and the mesh-architecture audit; (4) smallest extension as AD-025
§8.4 lists it — **without layers the behaviour is byte-identical** apart from the two additive export keys; not touched:
`Operation`, `OperationContext`, `HistoryStack`, `MeshDeltaCommand`, `MeshStateCommand`, `Scene`, `Selection`, every existing
signature (`add_vertex` gains a keyword with a default); (5) contract tests `tests/test_point_layers.py`,
`tests/test_mesh_change_journal.py` (layered random sequences, nested rollback, checkpoints, watches, copy-on-write),
`tests/test_layer_gate.py` (the app gate in `src/mirai/layer_declarations.py`, the `SessionStart` reader). Phase 5's
`split_face(…, origins=…)` is its own small entry (below).

**Decision:** AD-025 Phase 5 Knife origins (2026-10-27; [AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) §4.1
"Phase 5", §16; Manu's go for the Phase 5 Core change)

`Mesh.split_face(face_id, v_a, v_b, positions=(), origins=None)` gains the keyword `origins`: one `VertexOrigin` per
interior position, in path order, with any live vertices as sources (the Knife passes the barycentric weights of the hit
triangle over the original face's corners, which `split_face` never deletes). On a mesh with point layers it is required
for k ≥ 1 (else `MeshError`, the Phase 2 backstop with a new text); each origin is validated and combined like
`add_vertex(origin=…)` (`_origin_values`: live sources, finite weights, |Σw − 1| ≤ 1e-9, the `zero` rule) **before the
first mutation**, so a refusal leaves the mesh and the counters unchanged; the values are written through the one
journaled per-element path (`_write_value`), so Undo, rollback, Knife checkpoints and the file need nothing new. A wrong
length raises `MeshError` with or without layers; without layers the origins are otherwise ignored and the behaviour is
byte-identical. Freeze rule (§7): (1) requirement — the Knife on a mesh with morph targets (AD-025 Phase 5, H5a: topology
after morphs before skinning); (2) not solvable outside the primitive: `split_face` creates the interior vertices after
deleting the parent, and `add_vertex` cannot be called for them from outside (AD-017 K1: the Knife cuts only through
`split_face` / `split_edge`); (3) AD-025 §4.1 (the evidence for barycentric origins, X-10); (4) smallest extension — one
keyword with a default and its validation, no new record shape, no triangulation in the Core; not touched: every other
signature, the journal, `MeshDelta`, the file; (5) contract tests `tests/test_point_layers.py` (rule per layer incl. `zero`
and `()`, every refusal with mesh and counters unchanged, the length check without layers, Undo / Redo exact),
`tests/test_mesh_change_journal.py` (T-1: the layered random sequences call `split_face(…, origins=…)`), the Knife's
`tests/test_layer_knife.py` (T-6) and `experiments/knife_oracle/tests` (no layers there: unchanged).

**Decision:** AD-025 Phase 4 packed point-layer storage (2026-10-27; [AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md)
§4.2 "packed storage", §17; Manu's go for the Phase 4 Core internals, given with the Phase 4 assignment)

A Core-internal change behind the unchanged public API (§7: internals change when profiling justifies it). Each layer's
values were one `dict[VertexId, tuple]` (≈ 190 bytes per stored value); 50 dense targets on gollum_20k held **204 MiB**
against the 50 MB budget of the audit (§G), 50 on gollum (87.5k) 818 MiB [C]. New module `src/core/layer_storage.py`:
`LayerSlots` (one per mesh, `VertexId` → slot, **append-only** — a slot is never freed or reused, so a value array held by a
journal record or a history delta keeps its meaning without a journal of its own; AD-001's "an ID is never an array index"
holds: the ID goes through the map) and `PackedValues` (a `MutableMapping` over three float64 per slot in one `array('d')`
plus a presence byte: 25 bytes per slot, values bit-exact). `core/mesh.py`: `_layer_values` holds `PackedValues`
(`_packed` converts a plain dict at the one whole-layer entry `_bulk_set`), copy-on-write copies the buffers,
`map_vector_layers` maps a layer as whole buffers (`PackedValues.mapped`, the same per-component arithmetic), a load packs
the parsed values in one pass; `layer_storage_bytes()` is a read-only measuring aid. Freeze rule (§7): (1) requirement —
50 targets ≤ 50 MB at 20k (audit §G Phase 4), measured: 29.7 MiB for 50 dense, 25.7 MiB for 50 sparse; (2) no public
change can do it: the API returns values, the storage is internal; (3) AD-025 §4.2 / §17 and the measurements there;
(4) smallest change — not touched: every public signature, `MeshChange` / `MeshDelta` (their layer slots now hold
`PackedValues`, which compare equal to the dicts they replace), the file format, the journal's record shapes; (5) tests:
**every existing layer test and the T-1 / T-2 oracles unchanged and green** (`tests/test_point_layers.py`,
`tests/test_mesh_change_journal.py`), plus `tests/test_layer_storage.py` (dict semantics against a dict oracle through
random operations, equality incl. −0.0 and deleted slots, copy independence, the append-only map, 25 bytes per point).
Cost [C]: per-element reads ≈ 0.3 µs instead of ≈ 0.04 µs (a dense target written per element 11 → 37 ms at 20k); bulk
map 215 → 95 ms for 10 dense layers at 20k; details in AD-025 §17.

## 2. Was vor dem Freeze validiert wurde

### Phase A — Invarianten

- gültige Vertex-/Edge-/Face-Referenzen
- keine doppelten Vertices in Face-Boundaries
- bidirektionale Edge↔Face-Adjazenz
- keine Self-Loops
- maximal zwei Faces pro Edge für die V1-Manifold-Annahme
- keine stale Edge-Endpunkte nach Collapse

### Phase B — Topologie

`split_edge`, `collapse_edge` und `connect_vertices` wurden in relevanten Boundary-/Interior-/Fan-/Merge-Szenarien geprüft.

### Phase C — Identitätskontinuität

Für jede Topologieoperation wurden die vollständigen Mengen von Vertex-, Edge- und Face-IDs vor und nach der Mutation verglichen. Damit ist nicht nur die Existenz einzelner IDs, sondern auch nachvollziehbar, welche Elemente bleiben, verschwinden oder neu entstehen.

Der Core liefert dafür bewusst noch kein allgemeines Change-Set-/Provenance-System. Die vollständigen Diffs sind über die öffentliche Query-API extern rekonstruierbar.

### Phase D — Undo / Redo

Topologieänderungen können über `MeshStateCommand` mit Vorher-/Nachher-Snapshots exakt rückgängig gemacht und wiederhergestellt werden.

`Mesh.load_state()` stellt den Zustand in-place wieder her. Der ID-Allocator bleibt dabei monoton; Undo darf keine bereits verwendete ID erneut verfügbar machen.

Die Topologie-Mutationen bleiben bewusst History-unabhängig. Ein Aufrufer entscheidet explizit, wann eine atomare Mutation als History-Command erfasst wird.

### Phase E — Serialisierung

Scene-/Mesh-Zustände wurden nach echten Topologie-Mutationssequenzen per Dict und JSON roundtripped.

Geprüft wurden unter anderem:

- vollständige Topologiebeziehungen
- exakte Allocator-Zählerstände
- Kollisionsfreiheit für Vertex/Edge/Face-IDs nach dem Laden
- bewusster Ausschluss von Selection und History aus der Persistenz
- reservierte V1-Subsystem-Plätze für Morph Targets, Rig und Animation
- Versionsprüfung
- leere Scene

Die reproduzierbare Standard-Core-Suite umfasst **29 `unittest`-Tests**. Die Architekturverträge aus `tests/test_core.py` werden anschließend separat ausgeführt und enthalten zusätzlich die Basis-Serialisierungsprüfungen. Die dedizierten 8 Phase-E-Tests in `tests/test_scene_serialization.py` existieren als ergänzende, separat ausführbare Regressionstests, sind aber aktuell **nicht Bestandteil von `tests.run_core_suite`**.

**Gesamtergebnis der Standard-Suite:** 29/29 `unittest`-Tests + Architekturvertrags-Checks, PASS.

## 3. Architekturabgleich mit der langfristigen Vision

Die langfristige Vision ist kein größerer Modellierer um seiner selbst willen, sondern ein lebendes, erweiterbares 3D-System, in dem Modellierung, Deformation, Rigging, Morphs und Animation auf einer gemeinsamen Scene weiterarbeiten können.

Der V1-Core verbaut diese Richtung nicht:

- stabile opaque IDs schaffen eine Grundlage für spätere Referenzen
- kontrollierte Topologie-Queries verhindern, dass spätere Systeme von konkreten Containern abhängen müssen
- History und Serialization sind eigenständige Core-Verantwortlichkeiten
- UI, Viewport und Renderer sind nicht Teil des Core
- zukünftige Deformations-/Morph-/Rig-Systeme sind nicht vorweggenommen

Wichtig: **Stable IDs allein lösen noch kein Skin-/Morph-Remapping.** Bei zukünftigen Topologieänderungen wird voraussichtlich ein zusätzliches Change-/Provenance-/Remapping-Konzept benötigt. Dieses gehört in eine spätere, durch konkrete Anforderungen motivierte Phase.

Damit bleibt insbesondere der gewünschte langfristige Workflow möglich:

```text
Model
  ↓
Rig / Deformation testen
  ↓
fehlende Geometrie erkennen
  ↓
Mesh weiter bearbeiten
  ↓
Deformation / Animation weiterverwenden
```

Der V1-Core muss diesen Workflow noch nicht vollständig implementieren; er darf ihn aber nicht durch falsche V1-Annahmen unnötig verhindern.

## 4. Bewusst NICHT Teil des Freeze

Folgende Systeme werden nicht nachträglich in Core V1 hineingezogen:

- Half-Edge-/Winged-Edge-Neuimplementierung
- generisches Change-Set-System — *seit 2026-10-21 als Änderungs-Journal im Core (§7.1, AD-023 §9)*
- Herkunfts-/Provenance-Metadaten — *bleibt draußen: seit 2026-10-27 werden Herkünfte beim Erzeugen eines Vertex
  angewendet, nicht gespeichert ([AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) §4.1, §7.1)*
- Skin-Weight-Remapping
- Morph Targets — *Speicherung seit 2026-10-27 im Core als Punkt-Layer (AD-025 Phase 2, §7.1; seit Phase 4 gepackt, §7.1);
  Auswertung (die Mischung mehrerer Ziele), Editier-Ansicht und Gewichte bleiben außerhalb (`src/mirai`)*
- Rigging / Bones
- Animation
- Soft Selection / Influence-System
- vollständiges Extension-/Plugin-System
- AI-Integration
- Renderer
- UI / Viewport

Diese Punkte bleiben zukünftige Architektur- und Implementierungsaufgaben.

## 5. Konsequenz für `src/`

`src/core/` ist ab diesem Punkt **Referenz- und Vertragsbasis** für die nächsten Produktionsschichten.

Neue Produktionssysteme sollen den Core konsumieren, nicht ihn für jede neue UI-/Viewport-/Tool-Anforderung umbauen.

Grundrichtung:

```text
UI ──────────┐
             │
Tools ───────┼──► Core (FROZEN V1)
             │
Viewport ────┘
```

Die konkrete Produktionsstruktur außerhalb des Core wird erst aus den inzwischen gewachsenen Experimenten und echten Anforderungen abgeleitet.

## 6. Beziehung zu den Experimenten

Die Experimente bleiben bewusst erhalten. Sie sind Erkenntnis- und Validierungsräume, keine automatisch zu übernehmenden Produktionsmodule.

Insbesondere der Viewport-V1-Praxistest hat die Core→Viewport-Schnittstelle praktisch validiert, ist aber weiterhin ein Experiment.

## 7. Freeze-Regel für die Zukunft

Vor einer Änderung am gefrorenen Core gilt:

1. konkrete neue Anforderung benennen
2. prüfen, ob sie mit den bestehenden öffentlichen APIs lösbar ist
3. falls nicht: Architekturproblem dokumentieren
4. kleinste notwendige Core-Erweiterung bestimmen
5. Tests/Vertrag ergänzen
6. Änderung erst dann durchführen

Damit bleibt V1 klein, stabil und verständlich, ohne die Weiterentwicklung des Gesamtsystems zu blockieren.
