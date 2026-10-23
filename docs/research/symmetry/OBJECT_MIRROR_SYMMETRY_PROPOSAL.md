# Object-Level Mirror Symmetry — Design Proposal

**Status:** Proposal (Discovery, M5). **Nothing is built, nothing is decided.** Written 2026-10-23 as Track B of the
"Mesh Primitives, Object Deletion, Object-Level Mirror Symmetry" task; Track A (Add Mesh, Delete object) is implemented
([AD-021 §6.7](../../architecture/AD-021-OBJECT-COMPONENT-MODEL.md#67-track-a-implementation-note--add-mesh-and-delete-object-2026-10-23)).
**Evidence tags:** **[Code]** read in the repo at the commit of this document, **[Doc]**, **[Probe]** (scratch script, described
in §3, re-runnable from the description), **(Reading)** a derivation or judgement, `PROVISIONAL` every agent-set choice.
**Basis (only linked):** [AD-021](../../architecture/AD-021-OBJECT-COMPONENT-MODEL.md) (§4.2 ownership, §4.3 transform, §4.6
history, §4.8 space) · [AD-SYM-01](../../architecture/AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md) ·
[AD-SYM-04](../../architecture/AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md) · [SYMMETRY_EVOLUTION_RESEARCH](SYMMETRY_EVOLUTION_RESEARCH.md)
(AR-4, AR-12) · [CORE_V1_FREEZE](../../architecture/CORE_V1_FREEZE.md) §7.

---

## 0. Recommendation in one screen

1. **Smallest architecture that satisfies the eye workflow while keeping the two meshes independent: a *mirror pair* — two
   ordinary objects with their own meshes, plus one explicit, persistent, world-plane *placement coupling* between them**
   (option B below). The mirror copy command is the first half (option A); the coupling is the second.
2. **The coupling is on placement only** (translation, rotation, scale, pivot). It never touches a mesh. Editing either mesh
   afterwards is free; the geometry does *not* follow.
3. **The partner's transform is a pure function of the driver's transform** (`F`, §3): `t_B = H·t_A + 2d·n`, `R_B = H·R_A·H`,
   `s_B = s_A`, `pivot_B = H·pivot_A` for the world plane `n·x = d`, `H = I − 2nnᵀ`. `F` is an involution, so *either* side can
   be the driver, nothing accumulates, and Esc/Undo need no special case.
4. **Negative scale stays forbidden.** The reflection lives in the *geometry* of B: the mirror copy is a new mesh with
   reflected positions and reversed face winding. B's transform is still a proper rotation (`H·R·H` has det +1).
5. **One new thing in the Core:** a data-only list of pairs on `Scene` (+ file format v3, v2 still reads). Everything else
   is `src/mirai`: pure maths, three commands (mirror copy / pair / break), the partner-follow in the existing object
   gesture, and status lines. The mesh-level symmetry (`Shift+S`) is untouched.
6. **Open for Manu:** the Core addition (Go), keys/menu, what happens to Apply/Clear transform on a paired object, and whether
   a "re-mirror mesh" command is wanted (§9).

---

## 1. The required workflow

1. Create a Sphere (Track A: `Shift+A` → Sphere) and move it to one side of the character's centre (`4`, `W`).
2. Create a mirrored copy across a world plane, initially `X = 0`.
3. Explicitly establish a persistent mirror-pair relationship between the two objects.
4. Move either object — its partner follows *mirrored*.
5. The relationship survives Undo/Redo and scene save/load.

Evaluated in order: translation, then rotation and scale. A mirrored movement reverses the displacement normal to the plane
and keeps the tangential part; moving both objects by the same vector is not symmetry (§3 shows the difference with numbers).

The relationship is **never inferred** from positions (e.g. "two spheres roughly opposite"): a pair exists only because a
command created it, and a command that cannot establish it exactly says so.

---

## 2. What the code gives us today [Code]

| Fact | Where | Consequence |
|---|---|---|
| `ObjectTransform` = translation + rotation (orthonormal, **det +1** enforced, `ValueError` otherwise) + one uniform `scale > 0` | `src/core/scene.py:64-99` (`__post_init__`), AD-021 §4.3/Q-4 | A reflection cannot be a transform. Mirrored geometry has to be *mesh* data |
| World map `world(p) = t + c + s·R·(p − c)`; identity placement is an exact pass-through | `src/mirai/object_space.py:to_world` | The pair function `F` can be written against the existing formula and verified against it |
| Pivot `c` is per object, in object space; set today only by *Apply transform* (`pivot := old world pivot`), no pivot tool (Q-13) | `src/core/scene.py:SceneObject`, `Application._apply_transform` | Pair creation fixes `c_B = H·c_A`; nothing else can change a pivot while paired, except Apply (§5.7) |
| The object gesture writes `obj.transform` for every target on each motion and records **one** `ObjectTransformCommand([(obj, before, after), …])` on release; Esc restores every target's start instance | `Application._object_step` / `_object_release` / `_object_cancel` (`application.py` ~1368-1560), `scene_objects.ObjectTransformCommand` | The command already takes *N objects in one step*: the partner is one more entry. No new History mechanism |
| Rotate keeps the object's **world pivot position fixed** (`t + c` does not depend on `R`, `s`) | docstring of `_object_step` | The mirrored pivot position is preserved by `F` for free |
| The mesh-level symmetry is a `SymmetryDefinition` **on the Mesh**, in that object's coordinate space (plane through the object origin with an object axis as normal), cycled by `Shift+S` | AD-SYM-01, AD-021 §4.8 (Q-7), `Application._symmetry_cycle` | Different feature, different space, different key. Not reused, not reinterpreted |
| Partners under mesh symmetry already follow the **conjugated intent**: rotation by −angle about mirror(axis) around mirror(pivot), scale about mirror(pivot), computed as `mirror(T(mirror(p)))` so the partner is the *bit-exact* mirror | `CORE_V1_FREEZE.md` §7.1, "AD-SYM-02 §2.4 follow-up" | The same principle, one level up. The proposal is that decision applied to placements |
| History is one linear `HistoryStack`; commands hold their target instances; `CompositeCommand` exists | AD-021 §4.6, `scene_objects.CompositeCommand` | Pair create/break and "delete a partner" are composites of existing pieces |
| `Scene.from_objects` keeps object ids from a file, but **`Application.replace_scene` re-allocates ObjectIds on load** (ids in a file are session-local) | `src/core/scene.py:167`, `scene_objects.replace_scene` | A stored pair must be **remapped** by `replace_scene`, or it would point at wrong objects. This is the one trap in "save/load" |
| Scene file v2 stores per object `id/name/state/transform/pivot/mesh`; `morph_targets`/`rig`/`animation` are reserved `None` places | `src/core/serialization.py` | A named place for pairs follows the established pattern (a fixed field, not a framework) |
| References are locked (no transform gesture) | AD-021 Q-1, `_object_targets` | A Reference cannot be a driver or a follower; §5.7 |
| `Delete` in `4` removes selected objects, one Undo step (Track A) | AD-021 §6.7 | The partner-deletion rule (§5.5) extends that command |
| Object ids/instances survive Undo/Redo (`AddObjectCommand`, `DeleteObjectsCommand` hold the instances) | AD-021 §4.5/§6.7 | A pair may refer to ids; a pair never needs to hold an object instance |

---

## 3. The mathematics (derived, then probed) [Probe]

World plane `n·x = d`, `n` a unit vector, reflection `S(x) = H·x + 2d·n` with `H = I − 2nnᵀ` (`H = Hᵀ = H⁻¹`, det −1).
For an axis-aligned plane `H` is `diag(±1)`.

**Pair relation.** Object A has `(t_A, R_A, s, c_A)` and the mesh `M_A`. B gets the mesh `M_B = H·M_A` (every position
reflected about the *object origin* with the same `n`, face winding reversed) and

```
t_B = H·t_A + 2d·n        R_B = H·R_A·H        s_B = s_A        c_B = H·c_A
```

Then `world_B(H·p) = S(world_A(p))` for every mesh point `p` (substitute `p' = H·p`; `H·R_A·H` is a proper rotation because
conjugation preserves the determinant). `F: (t, R, s, c) ↦ (H t + 2dn, H R H, s, H c)` is an **involution** (`F∘F = id`), so
the same function gives A from B.

**Translation.** A moves by Δ → `t_B` moves by `H·Δ`: the normal component is reversed, the tangential one kept. Probe: plane
`X = 0`, `t_A = (2, 1, −3)`, Δ = `(0.5, 0.25, −0.75)` → B moves by `(−0.5, 0.25, −0.75)`. The naive "same vector" would put B
at `(−1.5, 1.25, −3.75)`; the correct place is `(−2.5, 1.25, −3.75)`.

**Rotation.** `R_A' = Q·R_A` gives `R_B' = (H·Q·H)·R_B`: the partner turns by the *conjugated* rotation. `H·Q(a, θ)·H = Q(H·a, −θ)`.
So a turn about the **plane normal** by θ turns the partner by +θ about the same axis (the mirror image of a spin about the
mirror axis is the same spin), and a turn about a **tangential** axis by θ turns the partner by −θ (probe: 30° about X → B +30°
about X; 30° about Y → B −30° about Y, both to 1e-15). This is exactly the mesh-level rule (CORE_V1_FREEZE §7.1).

**Scale.** Uniform `s_B = s_A`; the world pivot positions stay mirror images (`t_B + c_B = S(t_A + c_A)`).

**Pivot.** `c_B = H·c_A` is part of the pair state, fixed at creation. The *world* position of the pivot is `t + c`, so a
gesture that keeps it (Rotate, Scale) keeps it mirrored.

**Exactness [Probe].** 500 random placements per plane (all three axes; random rotation, scale, pivot, translation; 5 random
mesh points each): for a plane **through the origin** (`d = 0`) `world_B(H·p)` equals `S(world_A(p))` **bit-exactly**
(`H` only flips signs, and the sums run in the same order); for an offset plane (`d = 0.75`) the worst deviation is
**1.8e-15**, not bit-exact (the `2d·n` term rounds). Consequence: for the eye workflow (`X = 0`) the placements are exact;
an offset plane is exact to float rounding and nothing here needs more.

(The probe script is scratch, not repo code; it re-implements `F`, builds the two objects with `SceneObject`/`ObjectTransform`,
and compares `object_space.to_world` against the reflected world point.)

**Why "function of the driver" and not "apply the same delta to B".** `t_B' = F(t_A')` is stateless: no accumulated float
drift over a long gesture, no ordering problem when both objects are selected, Esc restores both start instances like every
other target, and an out-of-sync pair is detectable by comparing `F(A)` with B (§5.7).

---

## 4. The three architectures compared

| | **A. One-time independent mirror copy** | **B. Two independent meshes + explicit paired-transform symmetry** (recommended) | **C. Linked / shared geometry or a live mirror representation** |
|---|---|---|---|
| What it is | a command that creates B with reflected geometry; no relationship | A **plus** a stored pair record and a partner-follow in the object gesture | B's mesh *is* A's mesh (one shared `Mesh`) shown reflected, or a render-time mirror of A |
| 1 sphere moved aside, 2 mirrored copy | yes | yes | yes |
| 3 explicit persistent pair | **no** | yes (the pair record) | implicit in the sharing |
| 4 move either, partner follows mirrored | **no** | yes (`F`) | yes for placement; geometry too |
| 5 Undo/Redo, save/load | trivial (just an object) | needs: Undo composites, file v3, `replace_scene` remap | needs more (shared mesh in the file) |
| Meshes stay independent and editable | yes | **yes** | **no** — edits go to one geometry; B is not independently editable (or A's edit is applied in B's reflected view) |
| Negative scale forbidden (Q-4) | respected (geometry baked) | respected (geometry baked) | **conflicts**: a live reflection needs either a det −1 transform or a new "mirrored" render/pick flag on the object |
| Core change | none | one data field (pairs) + file v3 | `SceneObject`/`Scene` would stop owning a mesh exclusively (AD-021 §4.2), a mirrored flag, a reflecting `ObjectSpaceCamera`, shared ID space for picking/selection |
| `src/mirai`/`src/viewport` change | one command | commands + gesture hook + status | renderer winding/culling, picking, Knife and tools through a reflected object space, symmetry definition per shared mesh |
| Fit to the eye workflow | half | **fits** | over-solves (eyes need separate pupils/lids, not live geometry sharing) |
| Reversible later | yes | yes (a pair can be broken; C can still be added on top) | hard |

**Reading.** C is the right answer to a *different* question (live geometry mirroring for asymmetric-edit-free parts, instancing
of repeated props) and AD-021 §4.2 already keeps "instancing possible later because the Mesh does not point back". It is not
needed for two eyes whose meshes the Artist will keep editing independently, and it would push a reflection into the picking and
tool paths that AD-021 L-5 deliberately keeps free of it. A alone cannot do steps 3-5. B is A plus the smallest possible
relationship.

---

## 5. The recommended architecture (B)

### 5.1 Storage and serialization

```
MirrorPair  (frozen value, Core data only)
    a: ObjectId           # the object that was driver at creation; the order carries no meaning afterwards
    b: ObjectId
    normal: Vec3          # unit world normal, axis-aligned in v1 (X, Y or Z)
    offset: float         # plane n·x = offset, 0.0 for X = 0
Scene.mirror_pairs: tuple[MirrorPair, ...]      # replaced as a whole by commands; default ()
```

- **One record per pair**, owned by the Scene (a per-object `mirror_partner` field would store each pair twice and could
  disagree with itself). Invariants checked in the Scene API: `a != b`, both ids exist, each object in **at most one** pair,
  both objects Normal at creation.
- **File format v3**: a top-level `"mirror_pairs": [{"a": 0, "b": 1, "normal": [1,0,0], "offset": 0.0}]` next to
  `morph_targets`/`rig`/`animation`. v2 files load with no pairs; v3 is written. `Scene.from_objects` takes the pairs and
  validates them. This is the `ObjectTransform`/M0 pattern: data in the Core, behaviour in `src/mirai`.
- **`replace_scene` must remap** pair ids from the loaded Scene's ids to the new ones (it re-allocates ObjectIds today);
  a test pins this. Selection and History are still not saved.
- A pair file whose placements are no longer mirror images (hand-edited, or from a future bug) loads **as it is** and is
  reported out-of-sync (§5.7); it is never silently "repaired".
- **Core change = the one decision for Manu** (CORE_V1_FREEZE §7: additive, contract-tested, like M0). No other Core file moves:
  no `Operation`, no `HistoryStack`, no `Mesh` change.

### 5.2 World plane versus object-local symmetry

The pair plane is a **world** plane (initially `X = 0`) because the relation is between *placements* of two objects in the
scene; neither object's local space is privileged. The mesh-level definition stays object-local (AD-021 §4.8: it must be, for
bit-exact partner pairs). The two never meet: the mirror copy builds a new mesh with **no symmetry definition** (its vertex ids
are fresh); the pair coupling reads only `Scene.mirror_pairs` and the two `ObjectTransform`s. `Shift+S` keeps its meaning and its
key; the object mirror gets its own commands (§5.8). Rotating a *mesh-symmetric* object does not move the pair plane, and
moving a *paired* object does not move the mesh plane.

### 5.3 Mirrored rotation, scale and pivot

`F` of §3, in `src/mirai/object_mirror.py` (pure functions, no Application): `mirror_placement(obj, plane) -> (ObjectTransform,
pivot)`, `mirror_mesh(mesh, plane) -> Mesh`, `pair_residual(a, b, pair) -> float`. Axis-aligned planes only in v1 (`H` is a sign
matrix, so exactness argued in §3 holds); a general plane is the same formula and only loses the bit-exactness claim.
Pivot: `c_B = H·c_A` at creation; the gesture never changes pivots (L-2). Rotate about a camera-view axis (the default
without an axis constraint) works unchanged: the partner's rotation comes out of `F`, not out of the gesture's axis.

### 5.4 How either side can be the manipulated side

- The pair is symmetric in storage; `F` is an involution. Whichever object the object gesture (`W`/`E`/`R` in `4`) drives, the
  other becomes `F(driver)` after each motion step. In `_object_step` that is one extra line per pair after the existing
  `obj.transform = …` loop; the follower is added to `gesture.targets` (start instance recorded → Esc exact).
- **Both selected:** the pair is treated as one unit. Deterministic driver = the lower `ObjectId` (status: `'eye.L' drives, 'eye.R'
  mirrors`). The user never gets "both moved by the same vector".
- **One selected:** it drives; the partner is **not** selected and not highlighted by default (an optional secondary tint of
  the partner is a UI decision, §9).
- A constraint (`X`/`Y`/`Z`, planes), Shift precision, Ctrl snap, Alt+orbit are properties of the *driver's* gesture; the
  follower just reflects the result.
- Non-uniform scale does not exist (Q-4), so there is no scale case that breaks the mirror.

### 5.5 History

- **One logical command per gesture.** The release records one `ObjectTransformCommand` whose `changes` list contains the driver
  and the follower: Undo/Redo move both, together, in one step. No new class; no change to `HistoryStack`.
- **Mirror copy** = one `CompositeCommand`: `AddObjectCommand` (the new object B with the reflected mesh) + `MirrorPairCommand(create)`.
  Selection becomes `{B}` or `{A, B}` (`PROVISIONAL`); it is one Undo step. Undo removes B and the pair, Redo re-inserts the same
  instance and id.
- **Pair two existing objects** (A drives, B is placed): a `CompositeCommand` of `ObjectTransformCommand` (B jumps to `F(A)`, an
  explicit and announced change: *"'eye.R' is placed at the mirror of 'eye.L'"*), an `ObjectPivotCommand` (B's pivot := `H·c_A`)
  and `MirrorPairCommand(create)`. B's scale becomes A's, too (part of the placement). Refused if either is a Reference, already paired, or
  the same object. The meshes are the Artist's responsibility; the command does not inspect them.
- **Break pair** = `MirrorPairCommand(break)`: both objects stay exactly where they are; one Undo step. This is also the
  documented way to move one object independently.
- **Deleting one partner (Track A `Delete`)**: the delete command becomes a `CompositeCommand` of `DeleteObjectsCommand` + `MirrorPairCommand(break)`
  for each affected pair; the status line says `Deleted 'eye.R' - mirror pair with 'eye.L' broken`. Undo restores the object *and*
  the pair. Deleting both removes the pair record with them. (Alternative considered and rejected: refusing to delete a
  partner; it would make the pair a trap.)
- Pair state is only ever changed by a command, so Undo/Redo can never produce an inconsistent pair/placement combination: the
  linear stack replays exactly the states that existed.

### 5.6 Representing mirrored geometry without negative object scale

Mirrored geometry is **in the mesh of B**: `mirror_mesh` builds a new `Mesh` via the public API
(`mesh_from_positions_and_faces`) from A's compacted vertex list with positions `H·p` and every face's vertex list **reversed**
(outward normals stay outward; the primitives of Track A are the test material). B's `ObjectTransform` is `F(A)`, a proper
rotation with `scale > 0`: Q-4, the Reset-XForm reasoning of AD-021 §4.3, `ObjectSpaceCamera`, picking and the component tools
all stay as they are. The cost is deliberate: B's mesh does **not** follow later edits of A's mesh. (An explicit *Re-mirror mesh
from partner* command — rebuild B's geometry from A's, one Undo step, loses B's independent edits — is a later, separate option.)
Vertex ids of the copy are fresh and dense; a persistent vertex correspondence (for weight or morph mirroring, see the Weight-/Morph-Mirroring
rows of [SYMMETRY_EVOLUTION_RESEARCH](SYMMETRY_EVOLUTION_RESEARCH.md)) is **not** created here and is out of scope.

### 5.7 When the relationship cannot be preserved — explicit feedback

Nothing is silently dropped or repaired. Every case posts a status line (`Application._set_status`, the mechanism all object
commands use) and, where it refuses, changes nothing:

| Situation | Behaviour | Status (wording `PROVISIONAL`) |
|---|---|---|
| Move/Rotate/Scale a paired object whose partner is a **Reference** (locked) | gesture refused | `Object move: 'eye.R' (mirror partner of 'eye.L') is a Reference - locked` |
| A pair whose placements are **out of sync** (loaded file, hand edit): driver gesture | refused until re-synced | `Mirror pair 'eye.L' / 'eye.R' is out of sync by 0.12 - Re-sync (B follows A) or break it` |
| *Apply transform* / *Clear transform* on a paired object (changes the placement and the mesh/pivot relation the pair assumes) | **refused in v1**; the text names the way out | `Apply transform: 'eye.L' is in a mirror pair - break the pair first` |
| Pair create: object already paired / a Reference / both the same | refused | `Mirror pair: 'eye.R' already belongs to a pair with 'brow.R'` |
| One partner deleted | pair broken in the same Undo step | `Deleted 'eye.R' - mirror pair with 'eye.L' broken` |
| File loaded with a pair id that does not exist | pair dropped on load, reported once | `Scene file: mirror pair refers to a missing object - ignored` |
| Mesh edit (modes `1`/`2`/`3`) on either partner | allowed; geometry is independent | none (by design); the status of the pair is unchanged |
| Component work does *not* move objects, so no pair is ever at risk from it | — | — |

*Apply/Clear on a pair* could be made to work for both objects together when the plane passes through the origin (`d = 0`: both
placements become identity and the relation `F` still holds, §3); it is deliberately left out of v1 (§9).

The display side of the feedback — a faint line/label or a partner tint in `4` — is a presentation question for Manu (§9); the
status line is the L-4-style first step AD-021 already chose for the placement marker.

### 5.8 Commands, keys, UI (all `PROVISIONAL`, Manu's call)

Object-level, `4` only, state-checked like `Alt+R`: **Mirror copy (X = 0)**, **Pair selected objects**, **Break pair**, and
**Re-sync**. Suggestion: one small menu on `Shift+M` (window level like `Shift+A`; `Shift+M` is unbound — the `M` key is the Morph
Lab bridge, so a bare `M` is taken), no `BindingSet` change. A key per command can follow once the menu has been tried.

---

## 6. Interactions with existing features

| Feature | Effect |
|---|---|
| Mesh-level symmetry (`Shift+S`, AD-SYM-01/04) | independent: per mesh, object space. The mirror copy carries no definition (the user can switch it on per mesh) |
| Edit object / modes `1`/`2`/`3` | a paired object can be the edit object; its mesh edits do not affect the pair |
| Soft Selection, Knife, Loop tools | object-space, per mesh; unaffected |
| Reference state (`Alt+R`) | a Reference cannot be driver or follower (§5.7); making one partner a Reference does not break the pair, it blocks the gesture with a status line |
| Apply / Clear transform (M2-3) | refused on paired objects in v1 (§5.7) |
| Scene save/load | file v3; `replace_scene` remap (§5.1) |
| Morph Lab bridge (`M`) | sends one object; pairs are not part of it |
| Track A Delete / Add | Delete composes with pair-break (§5.5); Add is unaffected |
| Selection highlight | pairs do not change selection semantics; the partner is not auto-selected |

---

## 7. Implementation plan (not started) and tests

| Slice | Content | Tests |
|---|---|---|
| **B1** Core data | `MirrorPair`, `Scene.mirror_pairs` + API checks, file v3 (v2 reads), contract tests | roundtrip, v2 loads, invalid pair rejected, ids never reused; Scene tests stay green unchanged |
| **B2** Maths | `object_mirror.py`: `mirror_placement`, `mirror_mesh`, `pair_residual` | involution; the §3 probe as a test (bit-exact for `d = 0`, 1e-12 otherwise); translation normal reversed/tangential kept; rotation conjugation (normal axis +θ, tangential −θ); uniform scale; mirrored mesh: counts, winding, outward normals, closed ↔ closed (Track A's `test_scene_primitives` helpers) |
| **B3** Commands | `MirrorPairCommand` (create/break), mirror-copy composite, pair-existing composite, delete-with-pair composite, `replace_scene` remap | Add → Undo → Redo with ids; pair/break/Undo/Redo; delete a partner and Undo; save → load → pair intact and objects mirrored; Reference/duplicate/self refusals |
| **B4** Gesture | partner-follow in `_object_step`/`_object_release`/`_object_cancel`; refusals; Apply/Clear refusal | W/E/R on either side, both selected, one `ObjectTransformCommand` per gesture, Esc restores both, constraint axes, long-gesture drift = 0, Undo/Redo restore both; locked/out-of-sync refusals; mesh edit on a partner leaves the pair |
| **B5** Feedback + practical test | status lines, menu (`Shift+M`), one Artist test: two eyes | Manu's verdict; docs update |

The first three slices need no UI. Focused test files would be `tests/test_object_mirror.py` (B2), `tests/test_mirror_pairs.py`
(B1/B3), `tests/test_object_mirror_gesture.py` (B4); scope per AGENTS §8a: the Core change widens the run to `tests/` fully plus
the Lab trees.

## 8. Risks

| Risk | Mitigation |
|---|---|
| A Core file-format bump | additive v3, v2 still read, contract test, same path as M0; Manu's Go first |
| `replace_scene` id remap forgotten | explicit test; the loaded Scene keeps its own ids, the remap is one dict |
| Float drift or visible mismatch between partners | `F` is stateless and sign-exact for `d = 0`; `pair_residual` detects any mismatch; never repaired silently |
| The Artist expects geometry to follow too | stated plainly in the status/menu text; Re-mirror mesh as the explicit follow-up; linked geometry (C) remains possible later |
| Pair + Apply/Clear confusion | refused in v1 with the way out named |
| Two mirror concepts confuse users (`Shift+S` vs the object mirror) | different key, different word ("Mirror pair" vs "Symmetry"), different status prefix; documented in ATELIER when built |
| Offset planes are not bit-exact | accepted (1.8e-15); v1 ships `X = 0`/`Y = 0`/`Z = 0` |

## 9. Open decisions (for Manu)

1. **Go for the Core addition** (`Scene.mirror_pairs`, file v3)? Alternative: none without storing the relationship twice or
   outside the Scene file.
2. **Mirror copy selection result** and naming (`eye` → `eye.001`; or a side suffix `.L` / `.R`?).
3. **Menu/keys:** a `Shift+M` menu, or single keys? Bare `M` is taken by the Morph Lab bridge.
4. **Apply/Clear on a pair:** refuse (v1) or do both together when the plane is through the origin?
5. **Partner tint** in `4` and a visible plane marker: yes/no (look is presentation).
6. **Re-mirror mesh** command (copy A's geometry onto B again): wanted?
7. **General planes** (non-axis) and **a settable plane offset** later: needed for the character, or only `X = 0`?

## 10. Prior art (general knowledge, not re-verified in this session)

The major DCCs treat "mirror two objects" as a one-time clone with a mirrored transform (Max/Maya store a negative scale; Maya
and Blender users routinely freeze/apply it, which is the Reset-XForm problem AD-021 §4.3 avoids), as a modifier referencing a
mirror object (Blender), or as instances sharing geometry (Max Instance clone, Maya instance, Blender linked duplicate).
A *paired placement without shared geometry* is, in those tools, an add-on or a constraint rather than a core feature. The
closest in-repo precedent is the mesh-level "conjugated intent" rule (CORE_V1_FREEZE §7.1), on which §3 builds.
