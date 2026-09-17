I have the final evidence. Here is the audit.

---

# FINAL AUDIT — Shared Infrastructure / `src/` Gap Audit

*Read-only. No file was created, edited, moved or deleted. `git status --short` is empty; HEAD `b3f7344`. All inspections used `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`.*

---

## 1. Direct answers to the primary question

**Is `src/` actually missing shared infrastructure?**

**Partly yes — but much less than the borrow pattern suggests, and the shortfall is not where the architecture documentation says it is.**

Three different things are tangled in the hypothesis, and the repository gives a different verdict for each:

| Reading of the hypothesis | Verdict from evidence |
|---|---|
| "`src/` is thin because reusable capabilities stayed in experiments" | **Partly true.** A small, nameable set of capabilities is used by the live application but owned by experiments (all category **F**). |
| "`src/` is thin because it was never populated as intended" | **False.** `src/core` is deliberately narrow (domain only), and `src/viewport` explicitly owns derived geometry; both are documented decisions, not omissions. |
| "`src/` is missing whole *areas*" | **True for exactly three areas**, and none of them appear in `SOURCE_ARCHITECTURE.md §5`'s list of deliberately-undecided areas. |

**Which capabilities are already effectively shared infrastructure but live elsewhere? (Q1)**
Six, all category **F**: OBJ parsing · OBJ → Core Scene construction · mesh bounds · mesh center + radius · camera framing on bounds · the rigid-transform primitive. Plus one asset (the head basemesh) with three ownerless path constants.

**Which are reused across domains but should stay experimental? (Q2)**
`deformation.Transform` (EX-A reuse — but see below), the topology tools, the cylinder primitive, articulation. These are *research* capabilities consumed by research, not system capabilities.

**Which are genuinely production/system concerns with a natural home in `src/`? (Q3)**
Three, in order of strength:
1. **Mesh geometry queries** (`bounds`, `center`, `radius`) — pure functions over the public Core query API, no experiment-specific assumption.
2. **Camera framing / focus** — `docs/future_ideas/VIEWPORT_NAVIGATION.md:40-49` already names *"Orbit around Object / Zoom to Object / Zoom to Selection"* as a deferred navigation feature and states V1 deliberately keeps the scene centre. This is documented viewport/camera domain, not experiment domain.
3. **Import/asset path handling** (`file → Scene`) — `src/` currently has *no* file→Scene path at all (see §6).

**Which apparent duplicates are actually independent experiments? (Q4)**
Four cube builders, two cylinders, two face-normal algorithms (fan-first-triangle vs Newell), two triangulators (fan vs ear-clipping), two Core→Viewport bindings, and the two camera subclasses. None of these should be unified (details in §7).

**Which areas of `src/` are genuinely missing? (Q5)**
(a) an import/asset layer, (b) mesh-level geometry utilities, (c) camera framing/focus, (d) primitives beyond the cube, (e) a neutral home for Vec3 math. See §6 — with the important caveat that (e) is a *deliberate* duplication pattern, not an accident.

**Is `src/` "too thin", or is its size intentional? (Q6)**
**Its size is largely intentional.** `src/core` is documented as domain-only, `src/viewport` deliberately owns derived geometry (`derived.py:14`: *"Bounds/Normalen sind KEINE Topology"*), and `SOURCE_ARCHITECTURE §5` explicitly enumerates what stays undecided. What is *not* intentional is that three cross-cutting capabilities — geometry queries, framing, import — were never claimed by any layer, so the experiment that first needed them kept them. The architecture doc's open list covers window/entry point, event/input, command system, UI, document management and future subsystems — **it does not mention import, assets, bounds, framing or shared math.** The gap is real but unacknowledged, not planned.

---

## 2. What `src/` actually provides today (measured, not assumed)

| Package | Modules | Public surface relevant to sharing |
|---|---|---|
| `src/core` (9 modules, ~1,000 LOC) | `mesh`, `ids`, `scene`, `selection`, `history`, `operation`, `serialization`, `operations/{move,transform,topology}` | `Mesh` (query + mutation), `Scene`, `Selection`, `HistoryStack`, `Operation`, `scene_to_dict/from_dict/json` |
| `src/mirai` | `application`, `scene_factory`, `interaction/*`, `viewport/{camera,picking,display,vecmath}` | `Application`, `create_cube`/`build_cube_scene`, `BindingSet`/commands/ToolManager, `OrbitCamera`, `pick_*`, `DisplayState`, `vecmath` |
| `src/viewport` (8 modules) | `viewport`, `render_mesh`, `derived`, `overlay`, `resource_store`, `category`, `benchmark` | `Viewport`, `RenderMesh`, `DerivedGeometry`, `compute_bounds`, `triangulate_face`, `SelectionOverlay`, stores |

**Verified absences inside `src/`:**
- **No file→Scene path.** The only file I/O in all of `src/` is `src/mirai/interaction/input.py:309-314` (`keymap.json`). `src/core/serialization.py` is dict/JSON-string only — no `scene_to_file`/`scene_from_file`.
- **No OBJ importer or exporter.** A repo-wide grep for `save_obj|write_obj|export_obj|to_obj` returns nothing; exporting does not exist anywhere in the repository.
- **No mesh-level geometry utilities.** `src/core/mesh.py` exposes positions, adjacency and mutation only — no bounds, no normals, no centroid. `src/viewport/derived.py:90` has `compute_bounds(positions: list[Vec3])` (exported in `src/viewport/__init__.py:37`), i.e. an AABB over a *position list*, living in the render layer. There is no `bounds(mesh)`, no `center(mesh)`, no `radius(mesh)`.
- **No camera framing.** `OrbitCamera` (verified method list) has `orbit`, `dolly`, `eye`, `basis`, `build_view_matrix`, `build_projection_matrix`, `screen_to_ray`, `project_to_screen`, `pan`, `screen_delta_to_world` — no `frame()`/`fit()`/`focus()`.
- **No Vec3 math in a neutral layer.** It exists in `src/mirai/viewport/vecmath.py` (public, 8 functions) — a *viewer-state* package. Consequences: `src/viewport/derived.py:46-66` carries its own private `_sub/_cross/_length/_normalize`, and `src/core/operations/transform.py:47-72` carries its own `_add/_sub/_scale/_dot/_cross/_length`. **Both duplications are explicitly commented as deliberate** ("bewusst lokal und privat … der Core importiert keine Viewport-/Experiment-Module"; and the viewport package may not import `src.mirai`).
- **One primitive**: `create_cube`/`build_cube_scene` (`src/mirai/scene_factory.py`).

**What `src/` already provides *as shared infrastructure*, with real external consumers** (this is the counter-evidence to "too thin"):

| Production capability | External consumers |
|---|---|
| `mirai.viewport.picking` | `playground/selector.py:26`, `playground/window.py:116`, `lab/adapters/picking.py:22`, `tests/` |
| `mirai.scene_factory.create_cube` | `playground/tests/{test_presentation,test_selector}.py`, 8 production test modules |
| `mirai.interaction.tools.move.resolve_selection_vertices` | `playground/transformer.py:19` |
| `mirai.application.Application` | `playground/app.py:20` |
| `viewport.{Viewport,derived,resource_store}` | `playground/{app,renderer,vbo_builder}.py`, `lab/adapters/core_to_render.py`, `lab/report.py`, 5 lab test files |
| `mirai.viewport.vecmath` | `playground/camera.py:37` |
| `mirai.viewport.display.DisplayMode` | `playground/window.py` |

`src/` is therefore already the shared layer for picking, camera math, transforms, scene factory, viewport and display state. The unclaimed pieces are a *specific* set, not a general deficit.

---

## 3. Candidate classification (A–F)

| # | Capability | Location today | Class | One-line reason |
|---|---|---|---|---|
| 1 | OBJ parsing (`load_obj`, `ObjMeshData`) | `experiments/rigging-skinning-morphing/loaders/obj_loader.py` | **F** | Pure infrastructure parser, no research semantics; used by 3 areas |
| 2 | OBJ → Core `Mesh`/`Scene` | `lab/adapters/obj_to_core.py:40-66` | **F** | Application startup dependency of the Playground |
| 3 | Mesh bounds (`mesh_bounds`) | `lab/adapters/obj_to_core.py:74-82` (+ `rigging/viewport_adapter.py:73-81`) | **F** | Pure query over public Core API; 2 identical implementations; used by Playground |
| 4 | Mesh center + radius | `lab/adapters/obj_to_core.py:85-96` (+ rigging twin) | **F** | Same |
| 5 | Camera framing on bounds | `lab/adapters/obj_to_core.py:113-129` (+ rigging twin) | **F** | Playground runtime; camera-domain; already a documented future navigation idea |
| 6 | Head basemesh asset + its path constant | `rigging/meshes/head_basemesh.obj`; 3 constants | **F** (for the *path handling*), **C** (for the *file as research subject*) | Playground runtime asset, ownerless constant |
| 7 | Rigid transform primitive (`Transform`) | `rigging/deformation.py` | **B** | Reused by EX-A; research semantics still being explored; pure math, tiny |
| 8 | Vec3 math | `src/mirai/viewport/vecmath.py` + 2 private production copies | **A** (capability) / duplication is deliberate | Stable semantics; no neutral home; adding one is a new layer, not a fix |
| 9 | Topology tools (connect/loop/extrude/slide) | `playground/topology_tools/*` | **C/D** | Single research domain; ported from V1 by design |
| 10 | Cylinder primitive | `playground/experiments/articulation/demo_cylinder.py` (+ V1 open cylinder) | **C** | EX-A test body with a documented rationale |
| 11 | Articulation (EX-A) | `playground/experiments/articulation/articulation.py` | **C** | Research |
| 12 | Face normals (fan-first-triangle) | `src/viewport/derived.py:85-87` | **A** | Production-owned, correctly placed |
| 13 | Face normals (Newell) | `playground/topology_tools/extrude.py:42-57` | **C** | Different semantics — topology needs planar-face normals; not a duplicate |
| 14 | Triangulation (fan) | `src/viewport/derived.py:69-82` | **A** | Production-owned |
| 15 | Triangulation (ear-clipping) | `lab/adapters/triangulate.py` | **C** | Explicit research alternative, excluded from the production path on purpose |
| 16 | Core → Viewport binding | `lab/adapters/core_to_render.py` / `playground/renderer.py`+`app.py` | **D** + ownership **UNCLEAR** | Experiment-harness infrastructure vs a thin Playground passthrough |
| 17 | Lab GL harness, scene layer, report, probes | `lab/{integration,scene,report,run,_*}.py` | **D** | Harness infrastructure for one experiment |
| 18 | Playground window, HUD, ExperimentSlot, input map, selector | `playground/*` | **D** | Research-host infrastructure (the live application, by accident of history) |
| 19 | V1 modules with production counterparts | `experiments/mirai_bastel_viewport_V1/viewport/*` | **E** | Ancestors; one manual consumer (`rigging/run_viewport.py`) |
| 20 | Lab picking shim, lab camera override | `lab/adapters/picking.py`, `lab/lab_camera.py` | **E** | Superseded by production |
| 21 | `tests/{mesh,history,operations_init}.py`, `tests/mnt/**` | `tests/` | **E** | Dead/orphaned *(previously reported)* |
| 22 | V0.2 experiment package | `experiments/mirai_bastel_viewport_V02/*` | **E** | Superseded proof |

---

## 4. Detailed records — A / F candidates

### F-1 — OBJ parsing

| Field | Value |
|---|---|
| **Capability** | OBJ file → `ObjMeshData` (vertices + polygon faces), no triangulation, no materials |
| **Location** | `experiments/rigging-skinning-morphing/loaders/obj_loader.py` (~60 LOC; header states: *"reiner Parser ohne Abhängigkeit zu Core, Viewport oder pyglet"*) |
| **Current owner** | rigging experiment |
| **Actual consumers** | rigging `viewport_adapter.py:45`, `run_viewport.py`, `Tests/{test_obj_loader,test_viewport_integration}.py`; **Lab** `adapters/obj_to_core.py:31`; **Playground** transitively via `load_obj` behind `build_core_scene_from_obj` |
| **Crosses project boundaries?** | **Yes** — research → experiment-harness → live application |
| **Why shared** | Any code that must display or test against a real mesh needs it; nothing else can load geometry |
| **Semantics stable?** | **Yes** — documented scope (V before F, `v/vt/vn` tolerated, negative indices, no materials); parity asserted against core counts in `lab/tests/test_obj_to_core.py` |
| **Experiment-specific assumptions** | None found (deliberately: no Core/Viewport/pyglet import) |
| **Duplicates** | None in the repository (V1, V02, Lab, Playground have no loader) |
| **Natural `src/` domain** | An import/asset capability — conceptually production; **no existing `src/` module suggests a specific home**, so naming one would be premature |
| **Confidence** | HIGH (as F) |
| **Extraction currently safe?** | **Yes technically** (self-contained), but it changes the ownership contract of a file three areas rely on |
| **Prerequisites / unresolved** | Who owns it (this is the same open question as the head asset — both are "research track's asset layer"). The Playground's head path goes helper → loader → asset, so loader and asset should be decided together |

### F-2 — OBJ → Core Scene construction

| Field | Value |
|---|---|
| **Capability** | `obj_data_to_core_mesh`, `obj_data_to_core_scene`, `build_core_scene_from_obj` |
| **Location** | `experiments/mirai_bastel_integration_lab/adapters/obj_to_core.py:40-66` |
| **Current owner** | Integration Lab (deliberately *not* the rigging adapter — its docstring: *"Der V1-Adapter wird deshalb bewusst NICHT importiert — er würde die V1-Abhängigkeit wieder hereintragen"*) |
| **Actual consumers** | Lab `scene/scene_objects.py:21`, `integration/lab_viewport.py`, `tests/test_obj_to_core.py`; **Playground `app.py:27-30` → `load_head()` at `:135` (runtime)** |
| **Crosses project boundaries?** | **Yes** — the only path by which the Playground can display a real mesh |
| **Why shared** | "Give me a Scene from a file" is a universal application entry point; the cube equivalent already lives in production (`scene_factory`) |
| **Semantics stable?** | **Yes** — vertex order preserved, polygons preserved, triangulation deferred to the render boundary (a documented cross-cutting rule) |
| **Experiment-specific assumptions** | None; but it *targets* `src.core`, which is why it cannot simply be swapped for the rigging twin (that twin targets the Core-V1 fork) |
| **Duplicates** | **Yes — a deliberate, documented duplicate** of `rigging/viewport_adapter.py:53-70` (same logic, different core). Category **B/C**, not accidental |
| **Natural `src/` domain** | `src/mirai/scene_factory.py` is the *only* existing structure that suggests itself (it already owns `create_cube`/`build_cube_scene`, and its docstring states the rule: *"Baut ausschließlich über die öffentliche Core-Mutation-API … genau wie ein späteres Import-System das tun würde"*) |
| **Confidence** | HIGH |
| **Extraction currently safe?** | **Yes**, if done together with the bound helpers **or** separately (they are independent functions) |
| **Prerequisites** | Loader ownership (F-1) — otherwise extraction only moves the borrow one hop |

### F-3 / F-4 — Mesh bounds, center, radius

| Field | Value |
|---|---|
| **Capability** | `mesh_bounds(mesh) → (min,max)`, `mesh_center_and_radius(mesh) → (center, radius)` |
| **Location** | `lab/adapters/obj_to_core.py:74-96`; identical twin at `rigging/viewport_adapter.py:73-95` |
| **Current owner** | Nobody — both copies are convenience helpers in adapters |
| **Actual consumers** | `frame_camera_on_bounds` (both copies), Lab `scene_objects`/tests, rigging tests, **Playground `app._frame_camera` (runtime, indirectly)** |
| **Crosses project boundaries?** | **Yes** |
| **Why shared** | Any consumer that must place a camera, fit a view, or report mesh statistics needs it |
| **Semantics stable?** | **Yes** — AABB over positions; documented as a pure Core query (`mesh.vertex_position`, `all_vertex_ids`) |
| **Experiment-specific assumptions** | None |
| **Duplicates** | **Two identical implementations** (fork-target and production-target). Also a *third* related piece: `src/viewport/derived.py:90 compute_bounds(positions)` — same math over a position list, but bound to the render layer and to `DerivedGeometry.bounds_min/max` |
| **Natural `src/` domain** | Production geometry/scene utility. Neither existing package clearly owns "geometry over a Mesh" (`src/core` is deliberately position-access only; `src/viewport` owns bounds *as a render fact*) → this is the case where the repository does **not** strongly suggest a home |
| **Confidence** | HIGH (gap), MEDIUM (destination) |
| **Extraction currently safe?** | **Yes** — no state, no imports beyond `math`, no GL |
| **Prerequisites** | A decision on whether mesh geometry queries belong to `src/core` (contradicts the freeze posture), `src/mirai` (viewer-side), or a new small layer |

### F-5 — Camera framing on bounds

| Field | Value |
|---|---|
| **Capability** | `frame_camera_on_bounds(camera, mesh, margin)` → sets `camera.target`, `camera.distance` from AABB centre + bounding-sphere radius, FOV-aware |
| **Location** | `lab/adapters/obj_to_core.py:113-129`; identical twin `rigging/viewport_adapter.py:112-129` |
| **Current owner** | Integration Lab (consumer-wise); origin is the rigging adapter |
| **Actual consumers** | Lab `integration/lab_viewport.py:243` (margin 1.4), `report.py`; **Playground `app.py:105` `_frame_camera()` (runtime)** |
| **Crosses project boundaries?** | **Yes** |
| **Why shared** | Without it, every viewer starts with the object off-screen (Lab docstring: *"Notwendig, weil der Head nicht um den Ursprung zentriert ist"*) |
| **Semantics stable?** | **Yes, and it is an already-documented product concept** — `docs/future_ideas/VIEWPORT_NAVIGATION.md:40-49` lists "Zoom to Object / Zoom to Selection" as deferred navigation, and `SOURCE_ARCHITECTURE.md:220-221` explicitly permits *"Bewährte Konzepte wie Kamera, Picking und Rendering … in eine passendere Produktionsstruktur"* |
| **Experiment-specific assumptions** | Only duck-typing (`target`, `distance`, optional `fov_degrees`) — which matches production `OrbitCamera` exactly |
| **Duplicates** | Two (fork copy + production-core copy) |
| **Natural `src/` domain** | **Camera/viewport-state domain** — the strongest of all candidates, because the concept is already documented as a navigation feature and the production `OrbitCamera` is the exact target type |
| **Confidence** | HIGH |
| **Extraction currently safe?** | **Yes** — pure function, duck-typed, no GL, no window |
| **Prerequisites** | Decide whether camera framing is a camera *method* (behaviour on `OrbitCamera`) or a free helper. Both are small; the current code is a free function |

### F-6 — Head asset + its path constants

| Field | Value |
|---|---|
| **Capability** | A real, non-trivial base mesh (326 vertices, quads + poles) used as a display/edit subject |
| **Location** | `experiments/rigging-skinning-morphing/meshes/head_basemesh.obj` (44,849 B); `head_basemesh.mtl` (95 B, **unconsumed** — the loader ignores `mtllib`); `basic head mesh.blend` (475 KB, source, unconsumed) |
| **Current owner** | rigging experiment |
| **Actual consumers** | rigging (`run_viewport.py`, 3 test files); Lab (`_paths.DEFAULT_HEAD_ASSET:40`, `scene_objects.py`); **Playground (`_paths.py:45` → `app.load_head()`)** |
| **Crosses project boundaries?** | **Yes** |
| **Why shared** | It is the only real mesh in the repository; the Playground's `H` key exists solely to show it |
| **Semantics stable?** | n/a (data) — but its *role* is dual: research subject for rigging, application asset for the Playground |
| **Experiment-specific assumptions** | EX-A deliberately does **not** use it as a bend body (`demo_cylinder` docstring explains why: 52 poles would confound the articulation question) |
| **Duplicates** | File: none. **Path constants: three** (`rigging/viewport_adapter.py:48`, `lab/_paths.py:40`, `playground/_paths.py:45`) — each module defines its own |
| **Natural `src/` domain** | **None.** Production currently contains no data assets at all. The repository *does* declare an area for this: **`examples/`** — currently a 2-line README (*"Beispielmodelle und kleine reproduzierbare Szenarien für Entwicklung und Tests"*) with no files |
| **Confidence** | HIGH (facts), LOW (destination) |
| **Extraction currently safe?** | Only after the owner decision — *this is the kind of change the previous audit flagged as "do not move research assets into production automatically"* |
| **Prerequisites** | Q-C from the previous report (who owns the head asset) |

### A-8 — Vec3 math (capability A, duplication deliberate)

| Field | Value |
|---|---|
| **Capability** | `add/sub/scale/dot/cross/length/normalize/distance` on `tuple[float,float,float]` |
| **Locations** | `src/mirai/viewport/vecmath.py` (public, 8 fns) · `src/viewport/derived.py:46-66` (private `_sub/_cross/_length/_normalize`) · `src/core/operations/transform.py:47-72` (private `_add/_sub/_scale/_dot/_cross/_length`) · plus copies in V1 `vecmath.py`, `playground` usages via production |
| **Current owner** | `src/mirai/viewport` (a *viewer-state* package) |
| **Actual consumers** | `src/mirai/viewport/{camera,picking}`, `playground/camera.py:37`, plus the two private copies above |
| **Crosses boundaries?** | Yes (three production packages, the Playground) |
| **Semantics stable?** | Yes |
| **Experiment assumptions** | None |
| **Duplicates** | 3 production copies — **but both extra copies carry explicit comments justifying them** ("bewusst lokal und privat … der Core importiert keine Viewport-/Experiment-Module", mirroring the documented rule that `src/viewport` must not import `src/mirai`) |
| **Natural `src/` domain** | Would require a *neutral* layer that both core and viewport may import — a new structural element |
| **Confidence** | HIGH that this is deliberate; MEDIUM that anything should change |
| **Should it be extracted?** | **This audit does not support doing so.** Each copy is ~15 lines of pure arithmetic; the duplication is a *consequence* of the boundary, and the project principle ("implement little, assume much"; no new mechanisms without an observed failure) argues against inventing a shared math layer for it. Record it as a **known, accepted cost**, not a gap |

---

## 5. The named candidates — verified individually

| Named example | Verified finding |
|---|---|
| `adapters/obj_to_core.py` | **Live application infrastructure in an experiment directory.** 144 LOC, 5 helper families. Imported by `playground/app.py:27-30` (runtime) and by the Lab. Its own docstring frames it as a Lab adapter — its *de facto* role is larger. Also the deliberate production-core counterpart of `rigging/viewport_adapter.py` |
| rigging `loaders/obj_loader.py` | **Pure infrastructure parser** with no Core/Viewport/pyglet dependency, used by 3 areas. The only OBJ reader in the repository; there is no writer anywhere |
| `frame_camera_on_bounds` | **Two identical implementations** (fork + production-core), consumed at runtime by the Playground, and conceptually a *documented deferred navigation feature*. Strongest promotion candidate |
| mesh bounds / center / radius | **Two identical implementations**; production has a *related but different* `compute_bounds(positions)` in the render layer. No `bounds(mesh)` anywhere in `src/` |
| `deformation.Transform` | **~40 lines of pure math** (`deformation.py` imports only `__future__`, `typing`). The Playground's *only* rigging dependency; its docstring documents both the reuse and the explicit non-reuse of `linear_blend_skinning`. Smallest leak in the repository |
| **primitives** | `src/` has exactly one (`create_cube`). The cylinder exists twice for research reasons (V1: open cylinder for loop/ring tests; Playground: capped Y-axis body for EX-A). No production need for more primitives has been demonstrated — leaving them alone is consistent with the project's principle |

---

## 6. Missing areas of `src/` — deliberate vs unacknowledged

| Area | Missing? | Classification |
|---|---|---|
| **Import (file → domain)** | **Yes, entirely.** No file→Scene path; the only file I/O in `src/` reads `keymap.json`. The only importer lives in an experiment | **Unacknowledged gap** |
| **Export** | **Yes, entirely.** No OBJ (or any file) writer exists anywhere in the repository | **Unacknowledged gap** (arguably fine — no consumer needs it yet) |
| **Asset handling / paths** | **Yes.** Three ownerless constants for one asset; `examples/` declared but empty | **Unacknowledged gap** |
| **Mesh geometry queries (bounds/center/radius)** | **Yes at Mesh level.** AABB-over-positions exists in the render layer only | **Unacknowledged gap** |
| **Camera framing / focus** | **Yes.** Documented as a *future navigation idea*, not as a current need | **Acknowledged as deferred (future_ideas), but not owned by any layer today** |
| **Primitives** | Only cube | **Deliberate thinness** |
| **Shared math** | Vec3 exists but in the viewer-state package; two deliberate private copies | **Deliberate duplication** (documented in comments) |
| **Authored/authoring model, UI, document/project management, event/input architecture, command system, window/entry point** | Yes | **Deliberate** — enumerated in `SOURCE_ARCHITECTURE.md §5` and `SOURCE_ARCHITECTURE.md` explicitly refuses to pre-create folders |
| **Render draw call** | Not in `src/` | **Deliberate** (Gate 5 scope; `Viewport.render()` documented as a stable no-op) *(previously reported)* |
| **Selection behaviour** | Not in `src/` | **Deliberate** — research lives in the Playground *(previously reported)* |

**Conclusion:** `src/` is thin in exactly the places the architecture document does not discuss, and appropriately thin everywhere the document does discuss. That is the single most useful result of this audit: the difference is not size, it is *which* small capabilities were never claimed.

---

## 7. Apparent duplicates that must NOT be unified

| Pair | Why not |
|---|---|
| `src/mirai/scene_factory.create_cube` · `lab/scene/scene_objects.CUBE_VERTICES` · V1 `demo_scene.build_cube_scene` · rigging `demo_mesh` | Four cube builders, because four *different* cores/baselines are involved (production core, production core with a different winding table, Core-V1 fork, rigging's own box). Lab `scene_objects.py:26` documents its table as *"bewusst identisch zum Rigging-demo_mesh-Boxmuster"* — convergent, not forked |
| `src/viewport/derived.triangulate_face` (fan) · `lab/adapters/triangulate.triangulate_polygon` (ear-clipping) | Different algorithms for different scopes; the ear-clipper is a deliberate research superset for concave n-gons, explicitly excluded from the production path (`core_to_render.py:16`) |
| `src/viewport/derived.py` fan normal · `playground/topology_tools/extrude.py` Newell normal | Different semantics: the render path needs a cheap first-triangle normal for *rendering*; topology needs an orientation-independent planar-face normal. Unifying would change one of the two behaviours |
| V1 cylinder (open, Z axis) · Playground cylinder (capped, Y axis) | Different research subjects with documented rationales |
| `lab/adapters/core_to_render.CoreRenderBinding` · `playground/renderer.py` + `app.py` | Different purposes (instrumented harness binding vs a thin notification passthrough). **However:** ownership is genuinely unclear — neither is marked authoritative *(carried over as open question Q-I)* |
| `LabOrbitCamera` · `PlaygroundCamera` | Both are now redundant overrides whose formula is identical to production's (after `bbeef97`). This is the one "duplicate" that is *not* an independent experiment — but it is also not a merge candidate; it is a redundancy to be decided |
| `lab/adapters/picking.py` · production `pick_nearest_vertex` | The shim is a documented transitional adapter (`C`), not a parallel implementation |

---

## 8. Shared assets & test infrastructure

| Item | Finding |
|---|---|
| Assets in `src/` | **None.** Production contains no data files. |
| `examples/` | **Declared for shared example models/scenarios, contains only a README.** An existing structural placeholder — the repository itself already names a place for this kind of material |
| Head asset | Lives in the rigging experiment; three path constants point to it; used by the live application. **No duplicate file.** Its `.mtl` and `.blend` companions are unconsumed by code |
| Demo/test meshes | cube (production code), cylinder (Playground research), quad fixture (`tests/mesh_invariants.build_quad_mesh`) |
| Test fixtures | Production has one proper shared helper: `tests/mesh_invariants.py` (`assert_mesh_invariants`, `build_quad_mesh`, `assert_id_monotonic`), reused by 5 production test modules. The Lab uses its own `scene_objects.build_cube_scene`; the Playground uses production `create_cube`. **No cross-experiment fixture sharing, and no gap** — each test area builds what it needs from its own core |
| Asset ownership model | **Absent but not hidden.** Nothing is buried; the problem is that one file has three owners-worth of references and no owner |

---

## 9. What should NOT be touched

1. **`src/core`** — its narrowness is a documented decision (positions via `vertex_position`, no derived geometry, no file I/O). Adding bounds/normals/import here would contradict `CORE_V1_FREEZE.md` and `V1_CORE.md` and would need an explicit architecture decision.
2. **`src/viewport/derived.py`'s placement of normals/bounds** — documented as *render-derived*, not topology. Do not relocate it to satisfy a general "geometry layer" idea.
3. **The three private Vec3 copies** — each carries an explicit comment justifying it; unifying them invents a new layer for ~15 lines.
4. **`exercises/…` — all research assets**: the head basemesh and its `.blend` provenance, `demo_cylinder`, the topology tools, articulation, the Lab's ear-clipping triangulator and its harness, the V1 `perf/` material, the Core-V1/V1/V02 packages, and the pending `decision.md` verdicts.
5. **`tests/mesh_invariants.py` and the production test suite** — the only cross-cutting invariant harness; 398 tests green.
6. **The four cube builders and two cylinders** — independent by design; unifying them would erase the reason each exists.
7. **`docs/future_ideas/VIEWPORT_NAVIGATION.md`** — it is the *source* that makes framing a documented future feature; it should not be edited to match the current borrow.
8. **`examples/`** — do not populate it as part of a cleanup; an empty declared area is not a defect, and filling it now would be designing architecture ahead of a decision.

---

## 10. Open decisions required before anything moves

These are the same questions the earlier audits raised, now narrowed to what this audit can prove:

**D-1 — Does a shared "import" capability belong to production at all?**
Evidence: `src/` has no file→Scene path, and the only importer is in an experiment. Counter-evidence: production currently has no need to load files (the Playground does, and the Playground is research). This is the gate for F-1, F-2 and the asset question.

**D-2 — Do mesh geometry queries belong to a production layer?**
Evidence: bounds/center/radius are needed by the live application and are duplicated twice outside `src/`. Counter-evidence: `src/core` deliberately offers no geometry helpers, and `src/viewport`'s own bound is render-derived. Answering this decides F-3/F-4 *and* whether the existing `compute_bounds` placement stays as-is.

**D-3 — Is camera framing a camera behaviour or a free helper?**
Evidence: `docs/future_ideas/VIEWPORT_NAVIGATION.md` names "Zoom to Object" as a deferred navigation feature; production `OrbitCamera` is the exact duck-type. This is the smallest and most self-contained candidate.

**D-4 — Who owns the head asset (and with it, the loader)?**
Evidence: one file, three path constants, one research owner, one application consumer, and an empty `examples/` area. Both previous audits raised this as a product/ownership question, not a technical one.

**D-5 — Is `deformation.Transform` a shared primitive or an EX-A detail?**
Evidence: ~40 lines of pure math; the Playground's only rigging dependency. Deciding "vendor it" vs "keep the contract" resolves the last Playground→rigging edge without touching the rigging research.

**D-6 (carried over) — Which Core→Viewport binding is authoritative?**
Not answered by this audit; the Lab's and the Playground's remain parallel.

---

## 11. Confidence summary for a later sorting pass

| Statement | Confidence |
|---|---|
| `src/` has no file→Scene path; the only file I/O in `src/` is `keymap.json` | HIGH (grep-verified) |
| `src/` has no OBJ importer **or** exporter; no writer exists anywhere | HIGH (grep-verified) |
| `src/` has no `bounds(mesh)`/`center(mesh)`/`radius(mesh)` | HIGH (verified against `mesh.py` and `derived.py`) |
| `OrbitCamera` has no framing/focus method | HIGH (`camera.py` method inventory) |
| Mesh bounds/center/radius and camera framing exist twice outside `src/` and are used at Playground runtime | HIGH |
| `frame_camera_on_bounds` matches a documented future navigation feature | HIGH (`VIEWPORT_NAVIGATION.md:40-49`, `SOURCE_ARCHITECTURE.md:220-221`) |
| The Vec3 duplication in `src/core` and `src/viewport` is deliberate and documented | HIGH (both comments read) |
| The four cube builders and two cylinders are independent, not accidental | HIGH (each has a documented rationale) |
| The head asset has no owner and three path constants | HIGH |
| `deformation.Transform` is pure math with no core coupling | HIGH |
| `src/`'s overall thinness is mostly intentional | HIGH (`SOURCE_ARCHITECTURE §5`, `CORE_V1_FREEZE`, `derived.py` scope) |
| Which `src/` package should own geometry queries / import | **UNCLEAR** — the repository does not strongly suggest a destination; `scene_factory` is the only structural hint, and it is an argument, not a decision |

---

### Bottom line for the cleanup phase

`src/` is **not** missing a system layer. It is missing **three small, nameable capabilities** that were never claimed by any layer and therefore stayed where they were first written: **import** (file → Scene, plus asset paths), **mesh geometry queries** (bounds/center/radius), and **camera framing**. Everything else that looks like borrowed infrastructure (`Transform`, topology tools, cylinder, articulation, harness windows, render bindings) is either a research capability correctly living in research, or a deliberate duplication justified in its own comments, or a documented historical ancestor. The correct output of this audit is therefore a short list of *ownership decisions* — not a new package tree.

**Repository unchanged.** `git status --short` is empty; HEAD remains `b3f7344`.