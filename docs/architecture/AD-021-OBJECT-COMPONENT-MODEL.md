# AD-021 — Object / Component Model (ARCH-01)

**Status:** **DECIDED — go for M0 (Manu, 2026-10-15, in the chat: "Go for M0")**, after the independent review CLAUDE-001
(ACCEPT WITH CHANGES, no blocker; every finding answered in §9 and worked into the text). Option B with the Core change of
§5 (CORE_V1_FREEZE §7 step 6 given); A′ is not taken. Q-1…Q-4, Q-9, Q-10 answered (Decision record); Q-5…Q-8 stay open for
M2. Where a section still says "proposed" or "proposal only", this status wins.
**Mode (M5):** Discovery, Type C (Architecture Gate). Decision document, no production code.
**Answers:** [ROADMAP §6 ARCH-01](ROADMAP.md#arch-01--object--component-model) ("Must answer" list) plus two questions from
the handoff: where the Reference state lives, and in which space symmetry and soft selection compute.
**Driving requirement:** add a second object to a scene (e.g. `gollum.obj`) and give it a Reference state, without blocking
later multi-object component editing or per-object transforms.
**Read at:** `main` @ `63bcf65`. Line numbers refer to that commit.
**Basis (binding, only linked):** [V1_SPEC](../V1_SPEC.md) §2 (key `4` = Object), §12, §15 · [V1_CORE](V1_CORE.md) (AD-001
stable IDs, never reused; AD-003 lifecycle) · [AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md) (symmetry definition
on the Mesh, because it is bound to the Mesh's ID space and the app swaps the Mesh instance) ·
[AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md) §3 · [AD-SYM-05](AD-SYM-05-WEIGHTED-TRANSFORMS-IN-CORE.md)
§3.1 · [AD-020](AD-020-SOFT-SELECTION-APP-PATH.md) E3 · [AD-012](AD-012-TRANSFORM-SPACE.md) (local space deferred to
ARCH-01) · [AD-014](AD-014_Core-Change-Basis-Parameter-for-ScaleOperation.md) · [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §7 ·
[REFERENCE_HARDWARE](REFERENCE_HARDWARE.md).

**Evidence tags** (as in AD-SYM-04/05): **[Code]** read at `63bcf65` (file:line), **[Doc]**, **[Probe]** (scratch script,
named in place, re-runnable from the description), **(Reading)** a derivation, `PROVISIONAL` for every agent-set choice.

## Decision record

| Date | Who | What |
|---|---|---|
| 2026-10-15 | Manu (chat) | **Q-1 = locked** (a Reference cannot be moved/rotated/scaled; only selected and its state changed) · **Q-2 = yes** (a Reference never blocks component picking of the edit object) · **Q-3 = yes** (state change and add object are each one Undo step) · **Q-4 = yes** (object scale uniform only) |
| 2026-10-15 | Manu (chat) | **Go for M0** (Option B, Core change per §5; not A′) · **Q-9 = yes** (adding an object leaves the camera where it is) · **Q-10 = yes** (`Space` menu: Shift+click adds the entry as Reference, a plain click loads as today) |
| — | Manu | open for M2: Q-5…Q-8 |

---

## 0. Inputs

### 0.1 Artist decisions (Manu, 2026-10-15) — not re-decided here

| # | Decision |
|---|---|
| A-1 | **First need:** add a second object to the scene and assign it a Reference state. |
| A-2 | **Reference object:** no component picking, but clickable on object level (to change its state again). |
| A-3 | **Long-term:** each object has its own transform and pivot (eyes, jaw/teeth). |
| A-4 | **Multi-object component editing** is wanted later (e.g. clothes + body); it must not be blocked, but is not needed now. |
| A-5 | **The transform level (object vs. component) must always be explicit and visible** (3ds Max "Reset XForm" experience). |

### 0.2 Engineering assumption to challenge

EA-1 (unconfirmed, from the handoff): direction `Scene → Object(Mesh, Transform)`, thin, no speculative component framework.
§3 compares it against three alternatives instead of assuming it.

### 0.3 Scope

**In:** the seven ROADMAP "Must answer" questions, Reference-state placement, the computation space of symmetry and soft
selection, at least two options with cost against the `scene.mesh` call sites and the serialization format, the migration
path from `Scene.mesh`.
**Not in:** implementation; the renderer look of a Reference (ghost / wire / transparent); gollum performance
(WP-VIEW-PERF-01); multi-object component editing itself; rigging, materials, ARCH-02.

---

## 1. What exists (facts)

**F-1 — One mesh per scene.** `Scene.__init__` holds `mesh`, `selection`, `history` and the three reserved `None` slots
`morph_targets`, `rig`, `animation` (`src/core/scene.py:24-34`). [Code]

**F-2 — IDs are per mesh.** Each `Mesh` owns three monotonic allocators (`src/core/mesh.py:103-105`); every new mesh starts
at 0, so `VertexId(0)` exists in every mesh. IDs are `int` subclasses: `VertexId(3) == EdgeId(3)`, and the app already
compares the type explicitly (`src/mirai/application.py:2471`). An ID identifies an element **only together with its mesh**.
[Code]

**F-3 — Selection holds bare IDs.** `Selection` has `mode`, three ID sets and one `hovered` ID; `SelectionMode.OBJECT`
exists (`src/core/selection.py:25-29`) but nothing in `src/` or `playground/` uses it (grep). `clear()` leaves `mode`
alone (`selection.py:67-70`). **Mode `4` is unwired, not just unused:** `_active_set()` maps `OBJECT` to a throw-away set,
so `set`/`add`/`toggle` are silent no-ops (`selection.py:42-47`); `_active_selection_contains` raises `KeyError` in mode `4`
(`application.py:239-247`); `_MODE_COMMANDS` has no mode-`4` entry (`:217-221`); every `1`/`2`/`3` press calls
`selection.clear()` (`:801-802`); `is_empty()` decides C → Knife (`src/mirai/topology/contextual_c.py:28`). [Code; review
CLAUDE-001]

**F-4 — History is already object-agnostic.** `HistoryStack` only knows the `Command` protocol (`src/core/history.py:29-40`);
every Core command holds its own target instance: `MeshStateCommand.mesh` (`src/core/operations/topology.py:49-53`),
`VertexTransformCommand.mesh` (`src/core/operations/transform.py:220-226`). `OperationContext.target` is `Any`
(`src/core/operation.py`), and no Core operation reads `Scene` (grep `scene` in `src/core/operations/`, `operation.py`: no
hit). [Code]
**[Probe P-1]** (`probe_history.py`, scratch): one `Scene.history`, a `MoveOperation` committed on mesh A, then a
`MeshStateCommand` (split_edge) on mesh B while `scene.mesh` is A. Undo, undo, redo, redo: B restored, A untouched, then A
restored; both redone exactly (a full `export_state()` comparison differs only in the ID counters, which stay forward —
AD-001 as intended; review CLAUDE-001). **One scene-level stack already undoes correctly across two meshes.**

**F-5 — The app knows only `scene.mesh`.** `init_scene` replaces the mesh instance (`application.py:616`, `:623`) and builds
one `Viewport(self.scene.mesh, …)` (`:631-638`); the commit boundary `_mesh_transaction` snapshots `self.scene.mesh`
(`:2218`); Undo/Redo rebuilds the one viewport because `HistoryStack` does not expose the undone command (`:2122-2131`);
the selection mirror stack snapshots mode + three ID sets (`:2248-2258`), one entry per `history.push()` (`:2136-2173`).
The `Viewport` is single-mesh and carries the Selection overlay (`src/viewport/viewport.py:105-118`); the Playground builds
its viewports with `selection=scene.selection` (`playground/app.py:127-204`). Scene loads go through the `scene.mesh` setter
(`application.py:616/623`, `playground/app.py`, `experiments/symmetry_lab/lab_scene.py:43`). [Code]

**F-6 — No model matrix.** The shaders take `u_view` and `u_proj` only (`src/viewport/gl_render_store.py:48-49`): mesh
coordinates **are** world coordinates today. Transform tools map the screen drag to a world delta
(`src/mirai/interaction/tools/move.py:268`, `camera.screen_delta_to_world`) and constrain on world axes (AD-012);
`space="local"` is explicitly "ARCH-01 dependent" (AD-012, Constraints). [Code, Doc]

**F-7 — Symmetry is exact in mesh coordinates.** E1: the plane passes through the **world** origin and its normal is exactly
one **world** axis (`symmetry_axis.py:8-9`, "Welt-Ursprung … Weltachse"; decided for the app as AD-SYM-04 Q-1 = E-1);
E3/E4: the seam is derived from coordinates that are exactly `0.0`, without tolerance (`src/mirai/symmetry_axis.py:8-14`).
AD-SYM-05 §3.1 proves pair-level bitwise identity of soft distances from exactly this property ("mirrored coordinate
differences only change sign"). The soft radius is stored "in world units", computed from the mesh bounds
(`src/mirai/soft_selection/settings.py:8`, `:42-44`; AD-020 E3). [Code, Doc]

**F-8 — Serialization is one-mesh, version 1.** `scene_to_dict` writes `"mesh"` plus the three reserved slots,
`FORMAT_VERSION = 1` (`src/core/serialization.py:22-33`). Its only callers are tests (`tests/test_scene_serialization.py`,
`tests/test_core.py`); the production app neither saves nor loads scene files. No scene file exists in the repository.
[Code, grep]

**F-9 — `scene.mesh` call sites** (measured: `grep -rn 'scene\.mesh\b' --include=*.py`, i.e. **lines**; `tests/` includes
`tests/_archive`). [Code]

| Where | Lines (occurrences, review CLAUDE-001) | of which assignments |
|---|---|---|
| `src/` total | **59** | 5 |
| — `src/mirai/application.py` | 29 | 2 (`:616`, `:623`) |
| — `src/mirai/interaction/tools/` (move 5, transform 9, scale 2, rotate 1) | 17 | 0 |
| — `src/mirai/topology/` (extrude 5, split, delete_dissolve, connect ×2) | 9 | 0 |
| — `src/mirai/scene_factory.py` | 2 | 2 |
| — `src/core/serialization.py` | 2 | 1 |
| `tests/` | 725 (731) | 13 |
| `playground/` | 292 (298) | 13 |
| `experiments/` (of which Symmetry Lab 196) | 275 (282) | 10 (Lab: 1) |

The handoff's "~69" is not reproduced by this grep; the order of magnitude holds. The non-assigning `src/` sites read "the
mesh the user is editing" (picking, transform, topology, soft, symmetry, knife), with two exceptions that in M1 mean "what
to draw/frame": the Viewport construction (`application.py:631-632`) and `frame_scene` (`:664`, Q-9). The five assignments
mean "load a new scene" (app, factories) or "load a file" (serialization), not "swap this object's Mesh" (§5.2, R-4).
(Reading, from the list)

**F-10 — Prior guidance.** The Core V1 review warns against `Scene = exactly one Mesh` **and** against "a generalized
multi-object Scene graph merely to anticipate this" (`docs/archive/core_v1/CORE_V1_REVIEW.md:361-371`). V1_SPEC §15 points
6/7 keep Selection and Serialization from being mesh-only. Open references to ARCH-01: symmetry scope
(`SYMMETRY_EVOLUTION_RESEARCH.md` AR-12 and §12 "Ist die Definition an Objekt, Mesh oder Geltungsbereich gebunden?"),
subdivision level per object (`SUBDIVISION_SURFACES_RESEARCH.md` D8), per-object render resources (AD-018 §2), local space
(AD-012). The Mesh keeps position access behind `vertex_position()` to leave room for a later deformation chain
Base → Morph → Skin → Subdivision (`mesh.py:14-17`). [Doc]

---

## 2. The placement rule (Reading)

AD-SYM-01 put the symmetry definition **into** the Mesh because it is bound to the Mesh's ID space, must die with a swapped
Mesh and must ride along in the Mesh snapshot that topology Undo restores. The same test, applied to every datum this gate
touches, sorts them into three homes:

| Home | What belongs there | Test |
|---|---|---|
| **Mesh** | topology, positions, symmetry definition; later anything keyed by element IDs (morph deltas, skin weights) | bound to the Mesh's ID space; must be in the Mesh snapshot |
| **Object** | which Mesh, its placement (transform, pivot), its role in the scene (state, e.g. Reference), its name | **not** bound to the ID space; must **survive** a Mesh swap; must **not** be in the Mesh snapshot |
| **Scene** | the set of Objects; which Object is the **edit object** (the one whose components modes `1`/`2`/`3` address) | scene-wide; persisted (a file opens on the object it was saved on, like Blender's active object); not a modeling Undo step (R-3) |
| **Selection / Application** | which objects are selected, which components, hover | transient session state (V1_SPEC §3), not persisted, not a modeling Undo step |

Everything below follows from this table.

---

## 3. Options

### 3.1 The four candidates

- **A — Reference list beside the one mesh.** `Scene.mesh` stays the only editable geometry; references are extra meshes in a
  list (on `Scene`, or only in `Application`). No Object concept.
- **A′ — Thin Object in the App only** (review CLAUDE-001 R-1). The same object table as B, but in `src/mirai`;
  `Scene` stays one-Mesh and the App re-assigns `scene.mesh` to the edit object's Mesh whenever the edit object changes
  (it already swaps it on load, F-5). No Core change.
- **B — Thin Object** (EA-1). `Scene → objects → SceneObject(mesh, transform, pivot, state, name)`; `Scene.mesh` survives as a
  compatibility accessor for "the mesh being edited".
- **C — Component framework.** An Object holds typed components (`Mesh`, `Transform`, later `Material`, `Skin`, …) looked up
  by type, with a registry for serialization (ECS-like).
- **D — The Mesh carries placement and state.** `Scene.meshes: list[Mesh]`; `Mesh` gains `transform` and `reference`.

### 3.2 Against the Artist decisions

| | A | A′ | B | C | D |
|---|---|---|---|---|---|
| A-1 second object + Reference | yes | yes | yes | yes | yes |
| A-2 click a Reference to change its state back | **no**: "back" means the reference becomes editable, but only `Scene.mesh` is editable; a second editable mesh is option B in disguise | yes | yes | yes | yes |
| A-3 own transform + pivot | **no** (nowhere to put it) | yes, until the first save: `Scene` cannot persist it | yes | yes | yes, but in the Mesh snapshot (below) |
| A-4 multi-object editing later not blocked | **blocked** (one editable mesh by construction) | only by moving the table into Core first | yes (§4.10) | yes | yes |
| A-5 level explicit | — | yes | yes: placement and geometry are separate objects (§4.3) | yes | **weak**: one `export_state()` snapshot holds both levels; a topology Undo restores placement too |

### 3.3 Cost and risk

| | A | A′ | B | C | D |
|---|---|---|---|---|---|
| Core change | none (App-only) or one `Scene` field | none | `scene.py`, `selection.py` (one field plus the semantics of `_active_set`/`clear`/`is_empty`, §5.1), `ids.py` (one type), `serialization.py`; **`Mesh`, `Operation`, `OperationContext`, `HistoryStack` and every operation untouched** | as B plus a component registry and a serialization registry | **`Mesh`** (the most-guarded Core class) plus `scene.py`, `serialization.py` |
| 59 `src` sites (F-9) | 0 | 0, but every edit-object change re-assigns `scene.mesh` and must reset everything bound to it (viewport, pick cache, soft radius) | **0 forced** (compatibility accessor, §5.2) | 0 behind the same accessor; the registry touches every new consumer | 0 behind an accessor |
| Serialization | none, or an additive key | none until the first save, then B's version 2 anyway | version 2 with a version-1 read branch (§5.3); no user files exist (F-8) | version 2 plus a per-component registry — V1_SPEC §12 rules out a plugin serialization framework | Mesh state grows; `FORMAT_VERSION` unchanged, but placement travels inside `"mesh"` |
| History | unchanged | unchanged; the object commands live in the App | unchanged (F-4); three small new commands (§4.6) | unchanged | unchanged, but every topology snapshot carries placement |
| Main risk | dead end for A-2/A-3/A-4; must be replaced, not extended | a second scene model outside Core that the first save or A-4 must replace (CLAUDE.md golden rule: no orphaned solutions); `Scene` stays "exactly one Mesh", against CORE_V1_REVIEW §12 | the compatibility accessor hides "this means the edit object" in old code (mitigation §5.2) | builds a framework no requirement asks for (ROADMAP ARCH-01: "driven by actual requirements"; Core V1 review §12) | Mesh stops being a topology model; a Mesh swap (`init_scene`, F-5) loses the object's placement and state; instancing (one mesh, two placements) excluded |

### 3.4 Result

**A** fails A-2, A-3 and A-4. **A′** meets M1 without any Core change, so CORE_V1_FREEZE §7 step 2 is **not** "unsolvable
without a Core change" — it is "solvable short-term in the App, rejected because": A′ builds a scene model that has to be
replaced (at the first save, or when A-4 arrives), while the review's prototype of B's Core change left all three test
trees unchanged (`tests` 3114 passed / 51 skipped, `playground/tests` 1241 passed, Symmetry Lab 455 passed / 4 skipped,
before and after — review CLAUDE-001 Q6). The risk A′ avoids is measured small; the cost it creates is certain.
**C** is B plus machinery without a requirement and against V1_SPEC §12. **D** is the
cheapest Core-wise only at first glance: it puts placement into the most-guarded class, couples it to topology snapshots
and loses it on every Mesh swap — the reverse of the AD-SYM-01 argument. **B** is the only option that meets all five
Artist decisions without touching `Mesh`, the operation lifecycle or History. Choosing A′ for M1 and deferring M0 stays a
legitimate staging if Manu prefers no Core change before his first practical test (§6).

---

## 4. Recommendation: Option B — the answers

> **An Object is a scene member that owns exactly one Mesh and places it in the scene. Geometry and everything keyed by its
> IDs stay in the Mesh; placement and role live on the Object; the Scene knows which Object is being edited; what is
> selected lives in the Selection.**

### 4.1 What is an Object?

A `SceneObject` (name `PROVISIONAL`; not `Object`, which shadows Python's `object`) with exactly these fields:

| Field | Meaning | Default |
|---|---|---|
| `id: ObjectId` | opaque, never reused (§4.5) | allocated by the Scene |
| `name: str` | display only, not identity (e.g. `"gollum"` from the file name) | file stem / `"object"` |
| `mesh: Mesh` | the object's geometry in **object space** | — |
| `transform` | placement object → world: translation, rotation, uniform scale (§4.3) | identity |
| `pivot` | point in object space that rotation and scale act about at object level | origin |
| `state: ObjectState` | `NORMAL` or `REFERENCE`; extensible later (hidden, locked) | `NORMAL` |

Nothing else now: no component dictionary, no hierarchy, no material. Each later system adds a named field when it is built
(the V1_SPEC §12 pattern: a fixed place, not a framework). A `parent` field for hierarchy (eyes on a head bone) is additive and
not decided here.

### 4.2 Who owns the Mesh?

The Object, exclusively (one Object ↔ one Mesh instance; no sharing now — instancing stays possible later because the
Mesh does not point back). `Mesh` itself does not change: it does not know it is in an Object, has no transform and no
state. AD-SYM-01 stays valid per object: each Mesh carries its own symmetry definition in its own ID space, and a Mesh swap
inside an Object still drops the definition with the old Mesh.

### 4.3 Where does Transform live, and how is the level kept explicit (A-5)?

On the Object, never in the Mesh. Mesh positions are object-space coordinates; the world position is
`world = transform(p)`, with rotation and scale about `pivot`. The exact composition formula (and whether rotation is a
matrix or a quaternion) is implementation (E-2).

**Transform shape: translation + rotation + uniform scale `s > 0`** (a similarity; Q-4 = yes, Manu 2026-10-15). It is
invertible, maps planes to planes and keeps angles, so every component computation in object space means the same shape
in the world. Three reasons, all from the Max "Reset XForm" experience:

- Non-uniform object scale turns a world rotation into a shear in object space (`S⁻¹RS` is not a rotation); normals and
  mirrors skew, and the user cannot see which level holds the distortion.
- A negative factor (also a uniform one) is a reflection: winding and normals flip — the other classic Reset-XForm
  trigger (mirroring at object level). Hence `s > 0`.
- Similarities compose to similarities, so a later `parent` (eyes on a head) never produces shear that no
  translation/rotation/scale can represent; hierarchy stays additive.

Uniform-only scale is also **load-bearing for L-5**: under it, a world rotation becomes an object-space rotation and a world
axis scale an object-space axis scale with an orthonormal basis (AD-014's `basis` parameter), so the Core operations stay
unchanged. Non-uniform object scale would need a Core-operation change and its own AD. Non-uniform shape changes are
component edits.

**Level rules** (binding once accepted):

- **L-1 One gesture writes one level.** Component tools (modes `1`/`2`/`3`) write Mesh positions/topology only; object tools
  (mode `4`) write `transform`/`pivot` only. No tool writes both.
- **L-2 Moving the pivot never rewrites Mesh positions.** The pivot is Object data; editing it leaves geometry, IDs, the
  symmetry definition and soft caches untouched.
- **L-3 Converting between levels is only an explicit command:** *Apply transform* (bake into the Mesh, transform becomes
  identity — one Undo step; what Max calls Reset XForm) and *Clear transform* (transform back to identity, the object
  jumps, the Mesh stays — named so that a Max user does not read it as Reset XForm, review R-10). Never implicit: not on
  import, not on symmetry, not on export.
- **L-4 Visible:** the active level is the selection mode (`4` vs. `1`/`2`/`3`), and an edit object whose transform is not
  identity is marked in the UI (presentation `PROVISIONAL`, slice M2, Artist question **Q-6**).
- **L-5 Component work computes in object space** (§4.8), so an object transform never changes what a component tool does to
  the shape; only the user's world-space input (drag delta, world axis, pivot) is converted into object space, in the tool
  layer, before the Core operation runs. Core operations stay unchanged (they already work in mesh coordinates, F-6).
  AD-012's deferred `space="local"` becomes "the object's axes". With a transform, the tool's anchor positions are mapped to
  world before the screen → world step (e.g. `move.py:268`) and the result back to object space.

### 4.4 How does component selection relate to object selection?

- **Edit object.** The Scene names the one object whose components modes `1`/`2`/`3` address: `Scene.edit_object_id:
  ObjectId` (name `PROVISIONAL`; on `Scene`, not in the Selection, so the Core accessor `Scene.mesh` never depends on
  transient state and a loaded file has a defined edit object — review R-3). Component ID sets stay bare IDs and are
  **always read together with the edit object** (F-2: an ID without its mesh is meaningless). Changing the edit object
  clears the component sets, the way a mode switch does today.
- **Object selection.** `Selection.objects: set[ObjectId]` is the active set in `SelectionMode.OBJECT` (key `4`, V1_SPEC §2):
  `_active_set()` maps `OBJECT` to it, so `set`/`add`/`remove`/`toggle` work in mode `4`. **`clear()` and `is_empty()` stay
  component-only** (C → Knife keeps its meaning, F-3); objects are cleared explicitly. Order for the Q-5 gesture: read
  `objects`, set the edit object, then clear the components. Hover in mode `4` holds an `ObjectId` (a distinct type; every
  hover consumer already checks types, `application.py:2471`, `overlay.py:171-245`).
- **Picking.** Component picking only ever looks at the edit object's Mesh. Object picking (mode `4`) looks at every object
  that is not hidden — **including References** (A-2).
- **Switching the edit object** (which gesture makes an object the edit object) is Artist UX for slice M2 (**Q-5**); slice M1
  has exactly one editable object, so it needs no gesture.
- **Selection stays out of the modeling History** (V1_SPEC §3). The app's selection mirror snapshot (F-5) gains
  `objects` and the edit object. Whether Undo therefore switches back to the object a step was made in is Artist UX
  (**Q-8**, slice M2; M1 has one editable object).
- **Drawing.** Only the edit object's render entry gets the Selection overlays; a Reference's entry gets none. Otherwise its
  elements whose integer IDs equal the selected/hovered ones would light up (F-2, F-5; review R-5). M1 test.

### 4.5 How are identities assigned?

- **Component IDs: unchanged.** Per Mesh, monotonic, never reused (AD-001). No scene-global element allocator: it would
  change `Mesh`, its `export_state()` counters and `load_state()`'s forward-only rule, and still would not tell which
  Object an ID belongs to. *Rejected* for that reason.
- **Object IDs: new, same contract.** `ObjectId`, allocated by the Scene from one monotonic counter, never reused in a
  session, serialized with its counter (AD-001 extended to objects). A deleted Object's ID is dead, never wrong.
- **A component handle across objects is the pair `(ObjectId, ElementId)`.** Nothing needs it now (one edit object); it is
  the form multi-object editing (A-4) and later skin bindings use.

### 4.6 How does History operate across objects/components?

One linear `HistoryStack` per Scene, **unchanged** (F-4, P-1): each command keeps its own target instance, so commands on
different objects interleave correctly on one stack. New commands, all plain `Command` implementations outside
`HistoryStack`:

| Command (names `PROVISIONAL`) | Holds | Undo |
|---|---|---|
| Object transform/pivot change | object, before/after transform and pivot | restores both |
| Object state change (Normal ↔ Reference) | object, before/after state | restores state (one Undo step, Q-3 = yes) |
| Add / remove object | the `SceneObject` instance | removes / re-inserts the **same** instance and ID (AD-001); add is one Undo step (Q-3 = yes) |
| Apply transform (L-3) | a `MeshStateCommand` + a transform command | both, as one entry |

The last row is the only composite: a small `Command` that holds a list and undoes it in reverse — no change to
`HistoryStack`. It is the project's **first** composite command; AD-SYM-01 §2.1 counted such a command as new architecture,
and it is accepted here deliberately because baking two levels is one intent (L-3). The same composite is how one intent across several objects becomes one Undo step later (A-4, §4.10).
**App consequences** (review R-9): every `history.push()`, object commands included, records one mirror entry with
`objects` and the edit object (the one-entry-per-push invariant, F-5); Undo/Redo refreshes the view of the object the step
touched, not "the" viewport; pruning after Undo drops dead `ObjectId`s from `objects`. Undoing "Add object" while that object
is the edit object makes the previous edit object current again (it is in the mirror entry). Detail for slice M1.

### 4.7 Where does the Reference state live?

On the Object (`state`), persisted with it, independent of the Mesh.

| | Object field (**chosen**) | Mesh field | App-only set of IDs | Display layer (Maya) |
|---|---|---|---|---|
| survives a Mesh swap | yes | no | yes | yes |
| in the file | yes | yes | **no** | yes |
| in the topology snapshot | no (correct: not ID-space data, §2) | **yes** (wrong level) | no | no |
| new concept | none | none | none | **yes** (layers — not required) |

**Operational meaning of `REFERENCE`** (rules; look out of scope):

- **RF-1** Drawn (look: separate topic).
- **RF-2** Never the edit object; invisible to every component path: hover, pick, knife snap, soft field, symmetry. For the
  Core this is structural (operations receive the edit object's Mesh as `target`, F-4, and a Reference can never be the edit
  object); for the App it is a rule with a test: a Reference's render entry gets no Selection overlay (§4.4 Drawing).
- **RF-3** Pickable in mode `4`, so its state can be changed back (A-2).
- **RF-4** Object transforms on a Reference are **refused**; it can only be selected and its state changed (Q-1 = locked).
- **RF-5** `PROVISIONAL`: the last editable object cannot be switched to Reference (refused with a status line), so slice M1
  never has a scene without an edit object. Manu can lift this in one sentence.
- **RF-6** A Reference in front of the edit object **never blocks** its component picking — you pick body vertices through
  a clothes reference (Q-2 = yes).

### 4.8 In which space do symmetry and soft selection compute?

**Object space — the Mesh's own coordinates — for both, and for every component computation.**

- **Symmetry.** E1/E3/E4 need exact coordinates without tolerance (F-7). **[Probe P-2]** (`probe_space.py`, scratch):
  `head_basemesh` is exactly mirrored in its own coordinates (145 of 145 pairs). Mapped to world by a 30° rotation about Y plus
  a translation and mirrored across the mapped plane, **only 30 of 145 pairs stay bit-exact** (worst deviation `8.9e-16`) and
  **only 20 of 36 seam vertices lie exactly on the plane**. World-space evaluation would report a perfectly symmetric head as
  `partial` just because the object was rotated. In object space the definition is unaffected by any object transform.
  **This amends E1** (AD-SYM-04 Q-1 = E-1, `symmetry_axis.py:8-9`): "world origin / world axis" becomes "the object's origin
  / one of the object's axes". While the transform is identity (M0, M1) both read the same; from M2 on, the plane rotates
  with the object. Artist-visible, so **Q-7**; the AD-SYM-04 and `symmetry_axis.py` wording changes in M2. This answers the
  object-vs-mesh part of AR-12/§12 of the symmetry research (scope: the Mesh of one Object, in that Object's space);
  several islands inside one Mesh stay open (AD-SYM-01 §4).
- **Soft selection.** AD-SYM-05 §3.1's pair-level bitwise identity rests on the same exactness, so the symmetric field must
  use object space too. Under a similarity transform, distances only scale by the uniform factor, and the radius is a
  percentage of the object's bounds (AD-020 E3), so the weights equal world-space weights up to rounding. `SoftSettings.
  world_radius` then holds object units (a rename for slice M2, no behaviour change while transforms are identity). A
  change of the edit object becomes a fourth radius event next to switch-on, step change and scene load
  (`_soft_refresh_radius`, `application.py:1845-1849`; review R-12).
- **One exception, open for A-4:** a falloff that crosses objects (body → clothes) has no common object space; it would
  need a world metric. Not decided; it belongs to multi-object editing.
- **World space stays at the edges:** camera, screen → world input, gizmo/overlay drawing; converted once in the tool layer
  (L-5) and in the renderer (model matrix).

### 4.9 What Deformation/Rigging boundary does this permit?

- **The Mesh is the editable base (rest) geometry in object space.** A deformation chain (morph → skin → subdivision,
  `mesh.py:14-17`) produces *evaluated* positions and never writes the Mesh. Evaluated geometry belongs to the Object
  (a future field), is derived, not serialized, not in History.
- **ID-keyed deformation data** (morph deltas, skin weights) follows the AD-SYM-01 rule (§2): it is bound to the Mesh's ID
  space, so its home is the Mesh or a structure inside the Object that is snapshotted with it — not `Scene`. The reserved
  `Scene.morph_targets` slot is not moved now (it is `None`); its move is decided when morph targets are built.
- **The rig stays scene-level** (`Scene.rig`): one rig spans several objects (body, eyes, teeth). A skin binding refers to
  `(ObjectId, VertexId)` (§4.5); both are never reused, so a binding is valid or dead, never wrong.
- **Rigid parts** (eyes, jaw/teeth, A-3) are Objects whose `transform` a future parent (bone or object) drives. Hierarchy
  is additive (`parent`), not decided here.
- **Animation** (a ROADMAP ARCH-01 driver): an object's `transform` and `state` are plain values on the Object, so a later
  `Scene.animation` can key them by `ObjectId` without a new boundary; keying component data follows the ID-space rule
  above.
- **Not decided:** editing on a deformed pose, remapping after topology change (ARCH-02), bind-pose storage.

### 4.10 What keeps multi-object component editing (A-4) unblocked

| # | Condition | Holds because |
|---|---|---|
| N-1 | A Core operation can run on any object's Mesh | `target` is the Mesh, no Core op reads `Scene` (F-4) |
| N-2 | One intent across two objects can be one Undo step | composite `Command` (§4.6), `HistoryStack` unchanged. AD-SYM-02 §3 point 1 ("one operation instance") then reads "one instance per object, one History entry" — an amendment for that later AD, not now |
| N-3 | Selection can hold components of several objects | component sets become keyed by `ObjectId`; the edit object + bare sets is the one-key case. **Rule from M0 on:** code never infers the object from an element ID and never keeps component IDs beyond one gesture without the object they belong to |
| N-4 | Symmetry per object | definition per Mesh (AD-SYM-01), object space (§4.8) |
| N-5 | Soft across objects | open (§4.8, world metric) |

---

## 5. Proposed Core change (proposal only)

CORE_V1_FREEZE §7: (1) requirement A-1…A-5; (2) **solvable short-term without a Core change (A′, §3), rejected because** A′
builds a second scene model outside Core that the first save or A-4 must replace, while B's Core change is measured
behaviour-neutral (review prototype, §3.4); option A fails A-2/A-3/A-4; (3) documented here; (4) smallest extension below;
(5) tests in §6; (6) change only after Manu's go.

### 5.1 The extension (names `PROVISIONAL`)

| File | Change |
|---|---|
| `src/core/ids.py` | `ObjectId` (opaque, own type); reuses `IdAllocator` |
| `src/core/scene.py` | `SceneObject` (§4.1, plus `ObjectState`); `Scene.objects: dict[ObjectId, SceneObject]`, an `ObjectId` allocator, `add_object` / `remove_object`, `edit_object_id` (§4.4); `Scene()` still starts with one empty, editable object that is the edit object — today's `Scene()` has one empty Mesh |
| `src/core/selection.py` | `objects: set[ObjectId]`; `_active_set()` maps `OBJECT` to it; **`clear()` and `is_empty()` stay component-only** (unchanged behaviour); objects are cleared explicitly (§4.4, review R-2) |
| `src/core/serialization.py` | version 2 (§5.3) |
| **not touched** | `Mesh`, `Operation`, `OperationContext`, `HistoryStack`, `MeshStateCommand`, `VertexTransformCommand`, every operation |

### 5.2 `Scene.mesh` as a compatibility accessor

`Scene.mesh` becomes a property: **get** = the edit object's Mesh (it fails loudly if the edit object is not in `objects`;
RF-5 keeps one editable object in M1), **set** = replace the edit object's Mesh (Object identity, transform, pivot and state
stay; AD-SYM-01's swap semantics stay). The review's prototype ran all three test trees unchanged through this accessor
(§3.4).

**Meaning of the assignments** (review R-4): the 54 reading `src/` sites mean "the mesh being edited" (F-9). The
assignments mean "load a new scene" (`application.py:616/623`, the two factories, `playground/app.py`,
`lab_scene.py:43`) or "load a file" (`serialization.py:40`). With one object both readings coincide, which is why nothing
breaks in M0. From M1 on, the app's scene load goes through an explicit **scene reset** (all objects replaced by one new
object; History is already reset there, so no orphaned "Add object" step remains), and the setter is reserved for "swap this
object's Mesh". Playground and Lab keep their one-object assignments unchanged.

Mitigation for the risk in §3.3: the property's docstring says "the edit object's Mesh, never 'the scene's geometry'"; new
code that needs another object names it (`scene.objects[oid].mesh`); a migration of the old sites to explicit names is
mechanical and only needed where multi-object editing (A-4) reaches them — not a precondition for M1 or M2.

### 5.3 Serialization

```text
{ "version": 2,
  "object_id_counter": n,
  "edit_object": <id>,
  "objects": [ { "id", "name", "state", "transform", "pivot", "mesh": <Mesh.export_state()> }, … ],
  "morph_targets": null, "rig": null, "animation": null }
```

`scene_from_dict` reads version 1 as one Normal object with identity transform that is the edit object. This is a
migration, if a one-branch one: `serialization.py:5-9` ("erweitert, nicht migriert") and the example in V1_SPEC §12 are
updated in the M0 commit (same-commit rule; review R-15); there is still no migration engine. `"mesh"` keeps its exact Mesh
format, including `"symmetry"`. Cost: no user files exist (F-8); exactly two tests assert a top-level `"mesh"` key
(`test_scene_serialization.py::…::test_reserved_subsystem_slots_present_and_null_in_v1`,
`test_core.py::test_ad001_serialization_roundtrip`; review prototype). *Rejected:* keeping version 1 and adding `"objects"`
next to `"mesh"` — two places for geometry, one of them stale.

### 5.4 What the app needs (not Core; per slice)

M1: scene reset on load and an add-to-scene entry (Q-10); one render entry per object (identity transform, so no model
matrix yet), the Selection overlays only on the edit object's entry (§4.4); mode `4` wired (`_MODE_COMMANDS`,
`_active_selection_contains`, F-3) with object picking; object commands with mirror entries and per-object Undo refresh
(§4.6); the command gate refuses component work and transforms on a Reference (RF-4). M2: model matrix in
`RenderMesh`/overlays (AD-018: one more declared resource), ray → object-space conversion in picking, world → object
conversion in the transform tools (L-5), object tools, pivot, the level marker (L-4), Apply/Clear transform (L-3), the edit
object as soft-radius event (§4.8), the E1 wording (Q-7).

---

## 6. Migration path from `Scene.mesh`

| Slice | Content | Acceptance |
|---|---|---|
| **M0** — Core (after Manu's go) | §5.1–§5.3: objects, `ObjectId`, `edit_object_id`, `Selection.objects`, compatibility accessor, format v2 | `tests/` fully green **without editing one existing test except the two serialization tests**; `playground/tests` and `experiments/symmetry_lab/tests` green; a v1 dict loads; new tests for: `ObjectId` never reused, add/remove/re-add keeps the instance, a Mesh swap keeps state and transform, `clear()`/`is_empty()` unchanged, P-1 as a Core test (two objects, one stack) |
| **M1** — Artist need (A-1, A-2) | add a second asset (e.g. gollum) to the scene as Reference; it is drawn; mode `4` picks objects; a click on the Reference toggles its state; the Reference never lights up selected/hovered IDs; components of the editable object work as today | Manu's practical test |
| **M2** — placement (A-3, A-5) | object transform + pivot in mode `4`, model matrix, L-1…L-5, Apply/Clear transform, level marker | Manu's practical test; symmetry/soft bit-exactness on a rotated object (P-2 as a test) |
| later (A-4) | multi-object component editing: Selection keyed per object, composite intent, soft across objects (§4.10) | its own gate |

**Alternative staging (A′, §3):** M1 in the App only, M0 deferred to M2 or the first save. Recommended against (§3.4), but
it is Manu's call because the Core change is a Haltepunkt.

---

## 7. Questions

### 7.1 For Manu (Artist)

Answered 2026-10-15 (Decision record): **Q-1** a Reference is locked (only select + change state) · **Q-2** a Reference never
blocks component picking · **Q-3** state change and add object are Undo steps · **Q-4** object scale uniform only.

| # | Needed for | Question | Recommendation (`PROVISIONAL`) |
|---|---|---|---|
| Q-10 | M1 | How do you **add** an object instead of loading a new scene? | in the `Space` menu, Shift+click on an entry adds it as Reference; a plain click loads, as today |
| Q-9 | M1 | When an object is added, does the camera stay, or frame everything? (Loading a scene keeps framing the scene.) | the camera stays |
| Q-5 | M2 | How does an object become the one whose points/edges/faces you edit? | the object selected in mode `4` becomes the edit object when you press `1`/`2`/`3` |
| Q-6 | M2 | How should a moved/rotated/scaled object be marked, so the level is always visible? | status line text first; a better marker after the practical test |
| Q-7 | M2 | Symmetry (`Shift+S`) uses the **object's** axes: the plane rotates with the object. Today it is "world axis" (your E1 decision, AD-SYM-04). | yes — otherwise a rotated object is no longer exactly symmetric (§4.8, Probe P-2) |
| Q-8 | M2 | After editing two objects, does Undo switch back to the object the step was made in? | yes |

### 7.2 Engineering (agent domain, decided at implementation)

| # | Question |
|---|---|
| E-1 | Rotation representation (3×3 matrix vs. quaternion) and float exactness of `transform ∘ inverse` for picking |
| E-2 | Pivot composition formula and whether changing the pivot compensates the translation (object must not jump) |
| E-3 | `ObjectId` as an `ElementId` subclass or a separate base (`ElementId` is documented as "element"; nothing tests `isinstance(…, ElementId)`, review Q4) |
| E-5 | Undo refresh by object: is the mirror entry enough, or does a `Command` need to name its object? |

(E-4, framing, became the Artist question Q-9 — review R-8.)

---

## 8. Not decided here

Implementation and code names (all `PROVISIONAL`); the look of a Reference; gollum performance; hierarchy/parenting;
instancing; materials; morph/skin storage details; multi-object component editing and a cross-object soft metric; any key
binding beyond V1_SPEC §2's `4`; ARCH-02.

---

## 9. Review

**Independent review:** [AD-021_REVIEW_CLAUDE_001](../archive/object_model/reviews/AD-021_REVIEW_CLAUDE_001.md) (fresh-context
subagent of the authoring session, no chat or plan context; reviewed `ccr-0fd57631-0t6li6` @ `6a1669c`; archived unedited —
`ae591b8` caught a draft, `ad4ef47` is the reviewer's final text). Verdict: **ACCEPT WITH CHANGES**, no blocker. Confirmed:
both probes (exact numbers), the F-9 counts, every fact in F-1…F-8 and F-10 except the cites below, the B/C/D comparison,
coverage of all seven ROADMAP questions, the German restatement of A-1…A-5, and — by a prototype of §5.1/§5.2 in a scratch
copy — that the accessor leaves all three test trees unchanged and v2 breaks exactly two tests. Every finding below was
checked against the code before it was taken over. Manu answered Q-1…Q-4 during the review (Decision record); they match the
recommendations and change no finding.

| Finding | Severity | Answer |
|---|---|---|
| R-1 — Option A is a strawman; App-only A′ not compared; freeze step 2 not shown | major | **Taken.** A′ added to §3.1–§3.4 with its honest cost; step 2 restated in §5 ("solvable short-term, rejected because"); B stays the recommendation on the prototype evidence; A′ as staging named in §6 for Manu |
| R-2 — Selection extension under-specified; `clear()` on `1/2/3` collides with Q-5 | major | **Fixed, reviewer's form.** §4.4/§5.1: `_active_set` maps `OBJECT` → `objects`; `clear()`/`is_empty()` stay component-only; explicit object clear; Q-5 order stated; F-3 records the unwired mode `4` |
| R-3 — `Scene.mesh` depends on transient `Selection.edit_object` | medium | **Fixed:** the edit object lives on `Scene` (`edit_object_id`), persisted in v2; the getter fails loudly; §2 table gains a Scene row |
| R-4 — the setter means "new scene" at the load sites | medium | **Fixed:** §5.2 lists the meanings; M1 loads through an explicit scene reset; setter = swap this object's Mesh |
| R-5 — a Reference drawn with the shared Selection lights up colliding IDs | medium | **Fixed:** §4.4 "Drawing", RF-2, M1 acceptance |
| R-6 — E1 silently re-defined to object space | medium | **Fixed:** F-7 says "world"; §4.8 states the amendment of E1; Artist question **Q-7**; wording updates in M2 |
| R-7 — `s > 0`; uniform-only load-bearing for L-5; hierarchy/shear argument | medium | **Fixed** in §4.3 (all three; Q-4 answered yes, the cost of a "no" stated) |
| R-8 — Artist decisions in engineering text | medium | **Fixed:** Q-8 (Undo switches object), Q-9 (framing, was E-4), Q-10 (add gesture) in §7.1 |
| R-9 — mirror invariant for object commands; dead `ObjectId`s | minor | **Taken** into §4.6 |
| R-10 — "Reset transform" reads as Max Reset XForm | minor | **Taken:** renamed *Clear transform*; L-3 names Apply = Reset XForm |
| R-11 — Kurzfassung overstates "Undo und alle Werkzeuge unverändert" | minor | **Fixed** in the Kurzfassung |
| R-12 — edit-object change is a soft-radius event | minor | **Taken** into §4.8 and §5.4 |
| R-13 — F-9 counts lines; "no site means all meshes" | minor | **Fixed:** relabelled, occurrences added, the two draw/frame sites named |
| R-14 — cites; AR-12 overclaim; P-1 counters | nit | **Fixed** (`selection.py:67-70`, `application.py:2471`; "object-vs-mesh part of AR-12"; P-1 note) |
| R-15 — first composite command; v2 is a migration | nit | **Taken:** acknowledged in §4.6 and §5.3; V1_SPEC §12 and the docstring change in M0 |
| R-16 — AD-014 unused; animation driver | nit | **Fixed:** §4.3 (AD-014 basis carries axis scale), §4.9 (animation) |

The reviewer was a fresh-context subagent, not a separate claude.ai session. A second review is not required by the findings
(no blocker; each change is the reviewer's proposal or follows from it); Manu may ask for one in a separate session.

---

## Kurzfassung für Manu (Deutsch)

**Bitte zuerst prüfen — deine fünf Punkte, so wie ich sie verstanden habe:**

1. **Erster Bedarf:** ein zweites Objekt in die Szene holen (z. B. `gollum.obj`) und ihm den Zustand *Referenz* geben.
2. **Referenz-Objekt:** man kann keine Punkte/Kanten/Flächen darauf picken, aber das Objekt als Ganzes anklicken — um seinen
   Zustand wieder zu ändern.
3. **Langfristig:** jedes Objekt hat seinen eigenen Transform und Pivot (Augen, Kiefer/Zähne).
4. **Später** willst du Komponenten über mehrere Objekte hinweg bearbeiten (z. B. Kleidung + Körper). Das wird jetzt nicht
   gebaut, darf aber nicht verbaut werden.
5. **Die Transform-Ebene (Objekt oder Komponente) muss immer eindeutig und sichtbar sein** — deine Erfahrung mit
   „Reset XForm" in 3ds Max.

**Deine Antworten (2026-10-15):** Referenz ist gesperrt (nur anklicken und Zustand ändern) · man pickt durch eine Referenz
hindurch · „Referenz an/aus" und „Objekt hinzufügen" sind Undo-Schritte · Objekt-Skalierung nur gleichmäßig.

**Empfehlung in einem Satz:** Ein *Objekt* ist ein schlanker Behälter: genau ein Mesh plus Platzierung (Transform, Pivot),
Zustand (normal/Referenz) und Name. Das Mesh und die Werkzeuge rechnen wie bisher; neu ist nur, dass die Mauseingabe in die
Koordinaten des Objekts umgerechnet wird und Undo weiß, welches Objekt es neu zeichnen muss.

Was das für dich heißt:

- Werkzeuge in `1`/`2`/`3` ändern immer nur die Form, Werkzeuge in `4` immer nur die Platzierung — nie beides in einer Geste.
  Form und Platzierung werden nur mit einem ausdrücklichen Befehl verrechnet: „Transform übernehmen" (das, was in Max
  Reset XForm heißt). „Transform löschen" setzt nur die Platzierung zurück, das Objekt springt, die Form bleibt.
- Symmetrie und Soft Selection rechnen in den eigenen Koordinaten des Objekts. Ein gedrehtes Objekt bleibt dadurch exakt
  symmetrisch (in der Probe wäre ein um 30° gedrehter Kopf sonst als „teilweise symmetrisch" erkannt worden).
- Eine Referenz wird gezeichnet, ist für Punkte/Kanten/Flächen unsichtbar und lässt sich in `4` anklicken.

**Für den ersten Bauschritt mit Praxistest (M1) noch offen** (§7.1, Empfehlung jeweils dabei):
Q-10 *Wie fügst du ein Objekt hinzu?* (Vorschlag: im `Leertaste`-Menü Shift+Klick = als Referenz hinzufügen, Klick = laden
wie bisher) · Q-9 *Bleibt die Kamera beim Hinzufügen stehen?* (Vorschlag: ja).

**Später (M2), nur zur Kenntnis:** Q-7 die Symmetrie-Ebene dreht sich mit dem Objekt mit (heute: Weltachse, deine
E1-Entscheidung) · Q-8 Undo springt zum Objekt zurück, an dem der Schritt gemacht wurde · Q-5/Q-6 Objekt zum Bearbeiten
wählen, Markierung eines transformierten Objekts.

**Entschieden (2026-10-15):** Go für M0, Q-9 ja, Q-10 ja. — *Die Frage lautete:* Go für den Core-Schritt M0 (für dich unsichtbar, die Review hat ihn auf einer Kopie mit allen Tests
geprüft) — oder erst M1 nur in der App ohne Core-Änderung (Variante A′; ich rate ab, weil sie später ersetzt werden muss).

**Annahme, die du mit einem Satz korrigieren kannst:** Das letzte bearbeitbare Objekt kann nicht auf Referenz gestellt werden
(sonst gäbe es nichts mehr zu bearbeiten).

Keine praktischen Tests — das ist ein Entscheidungsdokument.
