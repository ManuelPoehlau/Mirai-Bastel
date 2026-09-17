All evidence gathered. Working tree verified clean (`git status --short` empty; HEAD `b3f7344`); all test runs used `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`.

---

# Ownership / Lifecycle Audit — V1 → Integration Lab → Playground

*Extends `docs/Repository_Wide Structural_Codebase_Health_Audit.md` and `docs/Experiment_Genealogy_Follow_up_Report.md`. Those conclusions are not revised; this report adds module-level ownership and lifecycle evidence.*

**Verification runs made for this audit (read-only):**

| Suite | Result |
|---|---|
| `experiments/mirai_bastel_viewport_V1/tests` | **184 passed + 21 subtests** |
| `experiments/mirai_bastel_integration_lab/tests` | **52 passed** |
| `experiments/rigging-skinning-morphing/Tests` (5 of 6 files) | **92 passed** |
| `experiments/rigging-skinning-morphing/Tests/test_topology_operations.py` | **uncollectible** — `pytest.fixture(skipif=…)`, lines 37/64 *(previously reported, not fixed)* |
| `tests/` (production) | 398 passed *(previous audit)* |
| `playground/tests` | 233 passed *(previous audit)* |

---

## 1. Executive Summary

1. **V1 is still practically needed — by exactly one manual GL window.** Repo-wide, the only code outside V1 that imports the V1 `viewport` package is `experiments/rigging-skinning-morphing/run_viewport.py:46-47` (`AllToolsWindow`, `TopologyWindow`). Everything else that mentions V1 is a docstring ("1:1-Logik-Port", "Migriert aus…").

2. **What keeps V1 alive is not research capability — it is a scene-loading convenience for manual inspection.** `run_viewport.py` builds the head basemesh with `viewport_adapter.build_scene_from_obj`, prints a report, and opens V1's All-Tools window so the artist can *look at* and *hand-edit* the head. It does **not** apply rig/deformation. The rigging experiment's actual research path is headless: `run_living_mesh.py` states *"Runs the interactive workbench **without viewport**"*.

3. **The Integration Lab is no longer primarily an experiment — it is a dependency container that still contains a live harness.** Its `adapters/obj_to_core.py` is a **runtime-critical Playground dependency** (`playground/app.py:27-30`, used at `:105` and `:135`). The rest of the Lab (harness window, scene layer, instrumentation, 52 tests) is Lab-only and has no external consumer.

4. **`obj_to_core.py` is itself a migration bridge that became load-bearing.** Its docstring says it deliberately re-implements the rigging `viewport_adapter.py` helpers *against `src.core`* specifically so that *"die V1-Abhängigkeit"* is not pulled in again. The Playground then imported that bridge — so the V1-avoidance work already exists, in the Lab, and is now used by the current application.

5. **Integration Lab → Playground migration is real but has one clear direction: capabilities migrated, implementations did not.** Window loop, GL draw, HUD and transform interaction were *re-invented* in the Playground, not derived. Only two Lab things are actually consumed by the Playground: `build_core_scene_from_obj` and `frame_camera_on_bounds`.

6. **The Playground's entire external footprint from `experiments/` is 3 symbols + 1 asset:** `build_core_scene_from_obj` (Lab), `frame_camera_on_bounds` (Lab), `Transform` (Rigging), and `meshes/head_basemesh.obj` (Rigging). It depends on no experiment *as a system*.

7. **`Transform` is the smallest and cleanest leak in the repository.** It is ~40 lines of pure math — `deformation.py` imports only `__future__` and `typing`, with zero Core/Viewport coupling — and it is the *only* thing the Playground needs from the rigging experiment.

8. **Asset ownership is ambiguous by triplication, not by burial.** The head asset is referenced by **three** independent constants (`experiments/mirai_bastel_integration_lab/_paths.py:40`, `experiments/rigging-skinning-morphing/viewport_adapter.py:48`, `playground/_paths.py:45`) pointing at the same file. The file itself lives in the rigging experiment. Nothing is "hidden" — it is explicitly named three times, which is the opposite problem.

9. **Two parallel "Core → production Viewport" bindings are alive simultaneously and neither is authoritative:** `experiments/mirai_bastel_integration_lab/adapters/core_to_render.py` (Lab, 253 lines, tracks resource ids/counters/material state) and `playground/renderer.py` + `playground/app.py` (thin passthrough, own `Viewport` construction). Neither references the other.

10. **Most important ownership ambiguity:** *Camera framing + OBJ→Scene construction* has no owner. It exists twice (fork-version in rigging, production-core version in Lab), is used by the live application from the Lab copy, and belongs to no `src/` module.

---

## 2. V1 Lifecycle

```text
Original purpose (2026-08-26)
  Prove the pipeline Scene → Mesh → Selection → Operation → Commit → History → Undo/Redo
  in a real GL window against the frozen Core-V1 — and later host the Topology Lab
        ↓
What migrated
  vecmath, camera, picking, display_state, commands, input_binding, default_bindings,
  tool(+ToolManager), move_tool, transform_tool  →  src/mirai/*            (documented promotions)
  test_camera_picking, test_input_binding, test_tool_lifecycle → tests/*  ("Migriert aus …")
  topology_tools, loop_ring, extrude_tool        →  playground/topology_tools/* (1:1 ports)
  selection behaviour, display modes, transform activation → playground/*  (re-invented)
        ↓
What remains (nothing outside V1 imports these except one launcher)
  viewport/all_tools_app.py    AllToolsWindow + AxisConstrainedMoveTool
  viewport/topology_app.py     TopologyWindow (scene= parameter, caption, tool set)
  viewport/app.py              original ModelerWindow
  viewport/constraints.py      Constraint enum + hotkey map   (never promoted as a module)
  viewport/demo_scene.py, topology_scene.py, topology_scene_cylinder.py
  perf/*                       6 scripts + 4 result files + PERF_BASELINE_REPORT.md
  tests/*                      15 files, 184 tests + 21 subtests, fully green
  SELECTION_MODES.md, WP-03 report, README
        ↓
Why it remains
  1. experiments/rigging-skinning-morphing/run_viewport.py:46-47 imports its two window classes
  2. Its own entry points (run.py / run_topology.py / run_cylinder.py / run_all_tools.py) + smoke scripts
  3. It is the ancestor reference for already-promoted src/mirai code (project memory, M1)
  4. Its perf/ area is the only performance evidence for the pre-V0.2 renderer
        ↓
What would free it
  Port run_viewport.py to a harness on src/viewport / the Playground host, and align
  viewport_adapter.py from mirai_bastel_core to src.core. Nothing else outside V1 needs V1.
```

### 2.1 Module-by-module: what V1 still provides (Q1)

| V1 module | Original purpose | Promoted to `src/`? | Promoted to `playground/`? | Current duplicate | Who imports/executes its capability today | Does the consumer need *V1's implementation*, or a *capability*? |
|---|---|---|---|---|---|---|
| `viewport/vecmath.py` | Vec3 tuple math | ✅ `src/mirai/viewport/vecmath.py` | – | production (superset) | V1 internals only | capability; production owns it |
| `viewport/camera.py` | OrbitCamera + ray/projection | ✅ `src/mirai/viewport/camera.py` | `PlaygroundCamera` subclasses **production**, not V1 | production | V1 internals + `run_viewport` **indirectly** (V1 tools take V1 camera) | production capability; V1 copy is the ancestor |
| `viewport/picking.py` | V/E/F picking | ✅ `src/mirai/viewport/picking.py` | yes, via production | production | V1 internals | production capability |
| `viewport/commands.py` | named commands | ✅ `src/mirai/interaction/commands.py` | – | production | V1 internals | production capability |
| `viewport/input_binding.py`, `default_bindings.py` | Input→Command + keymap overlay | ✅ `src/mirai/interaction/{input,bindings}.py` | Playground has an *independent, simpler* `PlaygroundInputMap` | production + playground | V1 internals | production capability |
| `viewport/tool.py` | Tool lifecycle + ToolManager | ✅ `src/mirai/interaction/tool.py`, `tool_manager.py` | – | production | V1 internals | production capability |
| `viewport/move_tool.py` | MoveTool + `resolve_selection_vertices` | ✅ `src/mirai/interaction/tools/move.py` | reused via production | production | V1 internals | production capability |
| `viewport/transform_tool.py` | TransformTool + Rotate/Scale + pivot | ✅ `src/mirai/interaction/tools/{transform,rotate,scale}.py` | reused via production | production | V1 internals | production capability |
| `viewport/display_state.py` | display modes | ✅ `src/mirai/viewport/display.py` | Presentation family (research) | production | V1 internals | production capability |
| `viewport/constraints.py` | axis/plane enum + hotkeys | ❌ as a module; axis *parameters* exist in production `RotateTool`/`ScaleTool`, **not in MoveTool** | ❌ | production has partial equivalent | V1 tests only | capability partially exists elsewhere — **unclear** |
| `viewport/topology_tools.py` | split/collapse/connect (Phase 1/3) | ❌ | ✅ `playground/topology_tools/connect_edges.py` (1:1 port) | playground port + V1 original | V1 owner only | no external consumer |
| `viewport/loop_ring.py` | loop/ring detection | ❌ | ✅ `playground/topology_tools/loop_ring.py` | playground port | V1 owner only | no external consumer |
| `viewport/extrude_tool.py` | single-face extrude |  | ✅ superseded by `playground/topology_tools/extrude.py` (multi-face) | playground superset | V1 owner only | no external consumer |
| `viewport/all_tools_app.py` | all tools in one window + `AxisConstrainedMoveTool` | ❌ | partially (Playground window has no axis-constrained Move) | playground window | **`rigging/run_viewport.py:46`** | **capability**: a tool-complete window |
| `viewport/topology_app.py` | Topology Lab window |  | partially | playground window | **`rigging/run_viewport.py:47`** | **capability**: same |
| `viewport/app.py` | original viewport window | partially → window-free `src/mirai/application.py` | – | production + playground | V1 `run.py`, `_smoke_wp01a.py` | no |
| `viewport/demo_scene.py`, `topology_scene.py`, `topology_scene_cylinder.py` | test scenes | ❌ | cylinder → playground `demo_cylinder` (independent build) | 4 cube builders (see §3.5) | V1 owner only | no |
| `perf/*` | performance research | ❌ (V0.2 architecture answered the question) | – | – | manual runs | research evidence — keep |
| `tests/*` | phase validation | 3 files migrated to `tests/` | topology tests re-written for playground | partial | V1 owner only | regression evidence for V1 — keep |
| `requirements.txt` | `pyglet>=2.0,<3.0` | – | – | – | V1 docs | – |

**Functional reason for the *one* remaining external dependency:** `run_viewport.py` needs a window in which (a) an externally supplied `Scene` can be displayed, (b) selection/topology/transform/display tools are simultaneously available, and (c) V1's tools accept that same Scene's core types. No other harness in the repository offers (a)+(b)+(c) at once — the Playground offers (b) but not (a)/(c).

---

## 3. Integration Lab Lifecycle

```text
Original purpose (2026-09-07)
  Integration harness / test studio: bring Production core + OBJ loader + head asset +
  V0.2 render proof + interaction experiments together in ONE practical GL test environment
        ↓
WP-IL-01 (2026-09-08): re-based on Production camera + Production viewport (`src/viewport`),
  V0.2 experiment no longer imported. Deliberately re-implemented the rigging adapter's
  helpers against `src.core` to avoid re-introducing the V1-Core dependency
        ↓
Bugfix session (2026-09-10): three GL bugs fixed (gl.Config removed, vsync, resize),
  merged to main — the Lab is the only place that has ever verified the production camera
  and production viewport on real GL
        ↓
What migrated into the Playground
  HUD idea (extracted, then independently extended)  •  presentation modes (as a research family)
  framing + OBJ→Scene helpers (IMPORTED, not migrated — the Playground uses the Lab's module)
        ↓
What was NOT migrated / what died
  the "would-be application" role: `integration/lab_viewport.py` (466 lines: window, draw, HUD,
  click-select, M-move, selftest, non-black-region pixel probe) lost to `playground/window.py`
        ↓
What remains today
  a live helper module consumed by the Playground, a Lab-only harness, a Lab-only scene layer,
  4 Lab-only adapters, 6 Lab-only scripts, 52 green tests, and one stale-but-referenced audit
        ↓
Why it remains
  `playground/app.py:27-30` imports `adapters.obj_to_core` — the Playground's head scene and
  camera framing depend on this directory being on sys.path
```

### 3.1 Module-by-module ownership (Q3)

| Lab item | Original purpose | Current purpose | Current consumer(s) | Consumer type | Equivalent elsewhere | Independently useful | Migration bridge? | Archive candidate? |
|---|---|---|---|---|---|---|---|---|
| `_paths.py` (34 L) | bootstrap | bootstrap + `DEFAULT_HEAD_ASSET` | Lab modules; **`playground/_paths.py` puts this dir on sys.path** | Playground (indirect) + Lab + Lab tests | `playground/_paths.py` | partially (asset constant only) | ✅ | after `obj_to_core` is extracted |
| `adapters/obj_to_core.py` (144 L) | OBJ→`src.core` + bounds/framing/counts, deliberately *not* the V1 adapter | same | `scene/scene_objects.py`, `integration/lab_viewport.py`, Lab tests, **`playground/app.py:27-30`** | **Playground runtime-critical** + Lab | rigging `viewport_adapter.py` (fork-version, parallel) | ✅ (used by the live app) | ✅ **it *is* the bridge away from V1-Core** | ❌ not until extracted |
| `adapters/core_to_render.py` (253 L) | V0.2 binding → re-based to production `Viewport`; `CoreRenderBinding`, `LabMaterialState`, `render_triangle_count` | Lab harness binding + instrumentation | `integration/lab_viewport.py`, `report.py`, 5 Lab test files | Lab only | **`playground/renderer.py` + `app.py` (parallel, simpler)** | ✅ for the Lab | ✅ (V0.2→production) | Lab-only; keep while harness lives |
| `adapters/picking.py` (52 L) | Lab's own vertex picking | **thin delegation** to production `pick_nearest_vertex` + 14 px threshold const | `integration/lab_viewport.py:49` | Lab only | production **is** the real owner | borderline (a shim) | ✅ transitional | ✅ after Lab archive |
| `adapters/triangulate.py` | ear-clipping for concave N-gons, "Superset" | deliberate Lab research alternative to the production fan | `tests/test_triangulate.py` only | Lab only | production fan path (`viewport.derived.triangulate_face`) is authoritative by decision | ✅ as research | ❌ deliberately outside the production path | keep / research |
| `lab_camera.py` (60 L) | V1-style GL view-matrix override | **now redundant** — production `build_view_matrix()` was fixed in `bbeef97` | Lab tests + harness | Lab only | production `OrbitCamera` (identical formula) | no longer | historical | archive candidate after verification |
| `scene/scene.py`, `scene/scene_objects.py` | multi-object Lab scene (`LabScene`/`LabObject`) + cube/head factories | same | `integration/lab_viewport.py`, `report.py`, 7 Lab test files | Lab only | production `scene_factory.create_cube` (cube only) | ✅ for the Lab | ✅ | Lab-only |
| `integration/lab_viewport.py` (466 L) | the actual GL harness: window, draw, labels, HUD panel, click-select, `M`-move, `--selftest`, non-black pixel probe | same | `run.py`, `report.py`, `_camera_motion_probe.py`, `_smoke_window.py` | Lab only | `playground/window.py` (much richer) | ✅ as a *minimal* reference harness | ❌ | **the "would-be application" that lost to the Playground** |
| `integration/lab_viewport_probe.py`, `report.py`, `run.py`, `_camera_motion_probe.py`, `_smoke_window.py` | cli / report / probes | same | Lab only | Lab only | – | ✅ | ❌ | Lab-only |
| `docs/ARCHITECTURE_RECONCILIATION_AUDIT.md` | Lab↔Production reconciliation; §A.1 camera finding referenced as SSOT | cited as SSOT by a research doc and by 3 code docstrings, but **predates the camera fix** | docs + comments | documentation | stale | historical evidence | ❌ | archive/annotate candidate *(already reported)* |
| `tests/` (9 files) | Lab verification | **52 passed, green** | Lab modules | Lab only | production tests exist separately | ✅ | – | keep while Lab lives |

### 3.2 Integration Lab vs Playground — migration classification (Q4)

| Capability | Lab implementation | Playground implementation | Classification |
|---|---|---|---|
| Window / event loop | `IntegrationLabWindow` | `PlaygroundWindow` | **PARTIALLY MIGRATED** (re-written, not derived) |
| GL draw call | own VBO build + own shaders inside harness | own VBO build (`vbo_builder.py`) + own shaders | **DUPLICATE** (two live draw paths, neither derived; both consume production `derived` data) |
| Camera object | production `OrbitCamera` + `LabOrbitCamera` override | production `OrbitCamera` + `PlaygroundCamera` override (+ yaw) | **DUPLICATE override**, now unnecessary in both |
| Camera framing | `frame_camera_on_bounds` (margin 1.25) | *imports the Lab's function* (margin 1.4) | **STILL LAB-OWNED (borrowed)** |
| Cube scene | `scene_objects.build_cube_scene` (own vertex table) | `Application.init_scene("cube")` → production `scene_factory` | **MIGRATED to production** (not *via* the Lab) |
| Head scene | `build_head_scene` → `obj_to_core` | `load_head` → **the Lab's `build_core_scene_from_obj`** | **STILL LAB-OWNED (borrowed)** |
| OBJ loading | via `loaders.obj_loader` (rigging) | same, transitively | **STILL RIGGING-OWNED** |
| Selection (state) | core `Selection` | core `Selection` | **SHARED via production core** |
| Selection (behaviour) | click-select + shift-toggle inside the harness | `playground/selector.py` (3 modes, box, component-aware) | **NOT RELATED** (Playground is the research home; Lab was a stopgap) |
| Transform interaction | `M` → `_move_picked_vertex`, **no history** | `X/R/S` hold → production tools → one history entry | **SUPERSEDED by Playground** |
| Topology interaction | absent | `K/I/J/G/E` tools + loop/ring select | **NOT RELATED** (Playground-only) |
| Presentation modes | own display toggle + highlight color | `playground/experiments/presentation/` (6 variants) | **MIGRATED as a research family** |
| Experiment hosting | absent | `Experiment` / `ExperimentSlot` / per-family registry | **NOT RELATED** (Playground-only) |
| HUD | labels + status line inside `lab_viewport.py` | `playground/hud.py` (extracted class, extended) | **MIGRATED** (extracted, then extended independently) |
| Core → viewport binding | `CoreRenderBinding` (resource ids, counters, material state, `sync`) | `PlaygroundRenderer` (4 notification methods + `sync`) + direct `Viewport(...)` in `app.py` | **DUPLICATE / parallel** — Lab's is more complete, Playground's is thinner |
| Instrumentation / reporting | `report.py` (headless perf + status), `--selftest`, pixel probe | none | **STILL LAB-OWNED**, Lab-only |
| Assets | `_paths.DEFAULT_HEAD_ASSET` | `_paths.DEFAULT_HEAD_ASSET` → same file | **DUPLICATE CONSTANTS, one file** |

### 3.3 What is *already* a Lab-owned thing that no longer needs the Lab
`adapters/picking.py` is a 15-line delegation to production. It adds a constant (`DEFAULT_PIXEL_THRESHOLD = 14.0`) that duplicates a production default. Its single consumer is the Lab harness.

### 3.4 What is *not* Lab-owned but looks like it
`adapters/obj_to_core.py` *contains* the Playground's head-scene path, but the file's stated purpose is "adaptation for the Lab". It has become dual-purpose: Lab helper **and** application infrastructure. That is the single most important finding in this section.

---

## 4. Rigging / V1 Dependency (Q2)

### 4.1 Exact dependency chain

```text
MANUAL VISUAL PATH (no automated coverage)
  experiments/rigging-skinning-morphing/run_viewport.py
    sys.path += (rigging, experiments/mirai_bastel_viewport_V1)          [:29-32]
    from viewport_adapter import DEFAULT_HEAD_ASSET,
                                  build_scene_from_obj,
                                  format_debug_report,
                                  frame_camera_on_bounds                 [:39-44]
    from viewport.all_tools_app import AllToolsWindow                    [:46]   ◄── V1
    from viewport.topology_app import TopologyWindow                     [:47]   ◄── V1
      → LivingMeshResearchWindow(AllToolsWindow)
          TopologyWindow.__init__(scene=scene) + _init_all_tools()
          frame_camera_on_bounds(self.camera, self.scene.mesh)
      → main(): build_scene_from_obj(DEFAULT_HEAD_ASSET) → print report → pyglet.app.run()

  viewport_adapter.py
    sys.path += (rigging, experiments/mirai_bastel_core_V1)              [:36-41]
    from mirai_bastel_core import Scene                                   [:43]   ◄── CORE-V1
    from loaders.obj_loader import load_obj                               [:45]

AUTOMATED RESEARCH PATH (headless, green)
  Tests/test_viewport_integration.py  →  viewport_adapter → mirai_bastel_core (core fork)
  Tests/{test_living_mesh, test_mutation_sequences, test_rig_controller,
         test_obj_loader, test_topology_operations}  →  bone/deformation/rig_controller/
                                                        loaders/src.core  (NO V1, NO fork-window)
  run_living_mesh.py      "Runs the interactive workbench WITHOUT viewport"      [:3]
  run_topology_survival_research.py, research_topology_survival.py  →  headless
```

### 4.2 The decisive fact

Repo-wide grep for imports of the V1 `viewport` package returns, outside V1 itself, **exactly two lines**, both in `run_viewport.py`. The rigging experiment's automated research does **not** import V1's viewport package at all. Its only fork dependency inside the tested path is `mirai_bastel_core`, via `viewport_adapter`, asserted by `test_viewport_integration.py::test_scene_is_viewport_core_scene`.

### 4.3 Does the rigging experiment need V1, or something V1 happens to contain?

| Dependency | Needs V1 specifically? | Functional reason | Exists elsewhere? | Active research or legacy infrastructure? |
|---|---|---|---|---|
| `viewport.all_tools_app.AllToolsWindow` | **No** — needs a tool-complete window that accepts an external Scene | display the head basemesh while hand-editing topology/selection/transform | capability exists in the Playground's window; **not** with (a) external Scene or (b) axis-constrained Move | **legacy visualization infrastructure** for an active headless research track |
| `viewport.topology_app.TopologyWindow` | **No** — same; provides the `scene=` constructor parameter the launcher exploits | same | same | same |
| V1 tools' operation on `mirai_bastel_core` types | **Yes, structurally** — V1's tools are typed to the fork; mixing core variants would break Scene/Selection/History consistency | internal consistency of one Scene | production tools are typed to `src.core`; the Lab's `obj_to_core` already ported the adapter helpers to `src.core` | **legacy runtime infrastructure** (decision explicitly deferred: *"ein Angleich ist eine spätere, bewusste Entscheidung"*, `viewport_adapter.py:17-22`) |
| `mirai_bastel_core` (Core-V1 fork) | **Yes** for the visualization path; **no** for the research modules (they use `src.core`) | `viewport_adapter` must build a Scene of the same class the window's tools use | production core | **intentional divergence**, documented |
| `loaders/obj_loader` + head asset | No — these are rigging's own | parse OBJ → polygons; the head is the research subject | production has no OBJ loader | **ACTIVE RESEARCH assets** (also borrowed by the Playground) |
| `deformation.Transform` (used by *Playground*, not by V1) | No — pure math | rigid rotation about pivot | nowhere else | **research helper, extractable** |

**Summary answer:** the rigging experiment needs *a tool-complete GL window over the same core it builds its Scene with*. V1 is simply the only remaining place that provides it, and the core it binds to is V1's own chosen fork. Neither requirement is a research requirement — both are consequences of "the visualization harness was never ported".

### 4.4 Is the rigging experiment still actively used for research?
Yes, with evidence: it is the technical track referenced from `docs/research/CHARACTER_SYSTEMS_RESEARCH.md` and from the Playground roadmap's EX-A section (which explicitly says the rigging experiment *"remains a separate technical research track"* and must not be pulled into the Playground unless the minimal bend probe requires it). Its headless suite is green (92 tests). Its `deformation.Transform` is already reused by EX-A. **Its V1 window is a viewing convenience, not the research apparatus.**

---

## 5. Playground External Dependencies (Q5)

### 5.1 Exact imports

| # | Import site | Symbol | Purpose | Runtime-critical? | Research or infrastructure? | Equivalent inside Playground/`src`? | Likely temporary? | Natural permanent owner |
|---|---|---|---|---|---|---|---|---|
| 1 | `playground/app.py:27-30` | `adapters.obj_to_core.build_core_scene_from_obj` | `load_head()` scene (`app.py:135`) | **Yes** | infrastructure | ❌ (production `scene_factory` has cube only) | **No** — it is the head path | `src/mirai/scene_factory` or Playground-local |
| 2 | `playground/app.py:27-30` | `adapters.obj_to_core.frame_camera_on_bounds` | `_frame_camera()` (`app.py:105`, margin 1.4) | **Yes** | infrastructure | ❌ | No | same |
| 3 | `playground/experiments/articulation/articulation.py:42` | `deformation.Transform` | rigid rotation about pivot in `_rotate_about_pivot` | Yes (EX-A) | **research helper (pure math, ~40 L)** | ❌ | **Yes** — thin, documented | Playground-local or a `src` math/util module |
| 4 | transitive via #1 | `loaders.obj_loader.load_obj` | OBJ parsing | **Yes** | infrastructure |  | No | rigging stays owner, or becomes shared data/loader |
| 5 | `playground/_paths.py:45` | `DEFAULT_HEAD_ASSET` → `experiments/rigging-skinning-morphing/meshes/head_basemesh.obj` | head scene asset | **Yes** | **asset** | ❌ (no duplicate file) | No | see §5.2 |
| 6 | `playground/_paths.py:28-41` | `sys.path` += integration_lab, src, repo root, rigging | import resolution for #1–#4 | **Yes** | infrastructure | – | follows #1–#4 | – |
| 7 | `playground/tests/*` (11 files) | `_RIGGING` on `sys.path` | make `deformation`/`loaders` importable in tests | Tests only | infrastructure | – | follows #3/#4 | – |
| 8 | `playground/tests/test_playground_camera.py:25-28` | `_LAB` on `sys.path` | make `adapters.obj_to_core` importable | Tests only | infrastructure | – | follows #1 | – |

**Answer to the key question:** the Playground is *not* depending on an experiment as a system. It is **borrowing three small capabilities** — (i) OBJ→Scene construction, (ii) camera framing on bounds, (iii) a rigid-transform primitive — **from two experiments that were simply where those capabilities were first written and never given a permanent home.** Item (i)/(ii) come from the Lab copy rather than the rigging original precisely *because* the Lab already ported them to `src.core`.

### 5.2 Asset ownership (Q6)

| Asset / helper | Original owner | Current consumer(s) | Research data or application infrastructure? | Duplicate? | Should remain in an experiment? | Plausible move |
|---|---|---|---|---|---|---|
| `experiments/rigging-skinning-morphing/meshes/head_basemesh.obj` (44,849 B) | rigging experiment | rigging (`run_viewport.py`, 3 test files), Lab (`_paths.DEFAULT_HEAD_ASSET`, `scene_objects`), **Playground (`playground/_paths.py:45`)** | **both** — research subject for rigging, application asset for Playground | file: no. **Path constant: three copies** (`lab/_paths.py:40`, `rigging/viewport_adapter.py:48`, `playground/_paths.py:45`) | **UNCLEAR** — needs a decision | Playground-local asset, or a shared assets location, or explicit "rigging owns it, others reference by contract" |
| `head_basemesh.mtl` (95 B) | rigging experiment | **no code consumer** (loader ignores `mtllib`; no material mapping) | neither | no | – | archive/keep as source data |
| `basic head mesh.blend` (475,928 B) | rigging experiment | no code consumer (source file) | source data | no | yes (provenance of the asset) | keep |
| `playground/experiments/articulation/demo_cylinder.py` | Playground | Playground (`app.load_cylinder`, tests) | application research asset, self-contained | no | yes (built for EX-A) | keep |
| `src/mirai/scene_factory.create_cube` | production | `Application.init_scene`, many production tests, Playground tests | application infrastructure | 4 cube builders exist (see §3.5) | n/a | KEEP (production is the right owner for the cube) |
| `frame_camera_on_bounds` | rigging `viewport_adapter` (fork version) → Lab `obj_to_core` (production-core version) | Lab harness + **Playground** | application infrastructure | **two implementations, same algorithm** | ❌ | `src/mirai` (scene/framing helper) or Playground-local |
| OBJ loader `loaders/obj_loader.py` | rigging experiment | rigging tests, Lab `obj_to_core`, **Playground transitively** | infrastructure (pure parser, no core/viewport/pyglet) | no | currently yes | UNCLEAR — "loader" is infrastructure, but it lives in a research experiment |

**No buried asset was found.** The feared pattern ("obsolete experiment, current app secretly depends on one random asset") does **not** apply: the head asset is referenced by three *explicit* constants in three modules, and the file is a deliberate research asset, not an accident.

### 4.5 / 3.5 Duplicate vs Ancestor Classification (Q7)

| Relationship | Category | Reasoning |
|---|---|---|
| V1 modules → `src/mirai/*` | **A. Historical ancestor** | documented promotions; production is the living version |
| V1 topology tools → `playground/topology_tools/*` | **A + C** | ancestor + documented 1:1 port re-targeted to `src.core`; V1 original deliberately retained |
| V1 `demo_scene.build_cube_scene` vs production `scene_factory.create_cube` vs Lab `scene_objects.build_cube_scene` vs rigging `demo_mesh` | **E. Independent experiment / convergent** | each targets a different core or baseline; Lab's comment says *"bewusst identisch zum Rigging-demo_mesh-Boxmuster"* — a deliberate reimplementation, not a fork |
| V1 `topology_scene_cylinder` (open, no caps) vs Playground `demo_cylinder` (capped, Y axis) | **E. Independent experiment** | different purpose (loop/ring tests vs EX-A bend body); playground's docstring justifies its own design |
| rigging `viewport_adapter.py` vs Lab `obj_to_core.py` | **B. Parallel implementation** — *intentional and documented* | separated by the core fork; `obj_to_core`'s docstring explicitly refuses to import the V1 adapter to avoid re-introducing the dependency |
| Lab `adapters/core_to_render.py` vs Playground `renderer.py` + `app.py` | **B. Parallel implementation** — parallel and *undocumented as such* | both bind core → production Viewport; Lab's is richer, Playground's thinner; neither references the other |
| `LabOrbitCamera` vs `PlaygroundCamera` vs production `OrbitCamera` | **B → now A** | all three view-matrix formulas are identical; the production fix made both overrides redundant |
| Lab `adapters/picking.py` vs production `pick_nearest_vertex` | **C. Transitional adapter** | explicit delegation shim; docstring says the Lab's own implementation "wurde als Duplikat von Production-Code entfernt" |
| Lab `adapters/triangulate.py` (ear-clipping) vs production fan triangulation | **E. Independent experiment** | explicitly kept outside the production path; different algorithm as research |
| Lab HUD (inside `lab_viewport.py`) vs `playground/hud.py` | **A. Historical ancestor** | extracted, then extended |
| `playground/experiments/articulation/_old_/{window,articulation,test_articulation}.py` vs current articulation | **F. Dead / orphaned** | committed as *"articulation old files"* (`f9b3ead`); nothing imports them *(previously reported)* |
| `tests/mesh.py`, `tests/history.py`, `tests/operations_init.py` vs `src/core/*` | **F. Dead / orphaned** | nothing imports them; `tests/mesh.py` cannot even be imported *(previously reported)* |
| `src/viewport` vs `experiments/mirai_bastel_viewport_V02` | **A. Historical ancestor** | V0.2 proof → production; V02 declares purpose fulfilled |

---

## 6. Ownership Map (Q8)

| Capability | Current owner | Consumers | Historical source | Status | Confidence |
|---|---|---|---|---|---|
| Scene construction (cube) | `src/mirai/scene_factory.py` | `Application.init_scene`, production tests, Playground tests | V1 `demo_scene` → production | **PRODUCTION-OWNED** | HIGH |
| Scene construction (head/OBJ) | **`experiments/mirai_bastel_integration_lab/adapters/obj_to_core.py`** | Lab + **Playground** | rigging `viewport_adapter.py` (port) | **EXPERIMENT-OWNED BUT APPLICATION-CRITICAL** | HIGH |
| Mesh loading (OBJ parse) | **`experiments/rigging-skinning-morphing/loaders/obj_loader.py`** | rigging tests, Lab, **Playground (transitive)** | rigging experiment | **EXPERIMENT-OWNED, shared infra** | HIGH |
| Camera | `src/mirai/viewport/camera.py` | production, Lab, Playground (subclass), V1 (own copy) | V1 `camera.py` | **PRODUCTION-OWNED** | HIGH |
| Camera view-matrix override | `playground/camera.py`, `lab_camera.py` (both redundant) | Playground, Lab | V1 finding | **UNCLEAR** (production now already correct) | HIGH |
| Camera framing | **`lab/adapters/obj_to_core.frame_camera_on_bounds`** (+ rigging copy) | Lab + **Playground** | rigging `viewport_adapter` | **EXPERIMENT-OWNED, application-critical, DUPLICATED** | HIGH |
| Picking | `src/mirai/viewport/picking.py` | production tests, Lab (via shim), Playground (`pick_component`) | V1 `picking.py` | **PRODUCTION-OWNED** | HIGH |
| Selection state | `src/core/selection.py` | everything | Core V1 | **PRODUCTION-OWNED (frozen domain)** | HIGH |
| Selection behaviour | **`playground/selector.py`** | Playground window | V1 `SELECTION_MODES` experiment | **PLAYGROUND-OWNED (research, no verdict yet)** | HIGH |
| Transform (semantics) | `src/core/operations/{move,transform}.py` | production tools, Playground | Core V1 + ADR-001 promotion | **PRODUCTION-OWNED** | HIGH |
| Transform (interaction) | `src/mirai/interaction/tools/*` (Playground reuses) | production tests, Playground | V1 `move_tool`/`transform_tool` | **PRODUCTION-OWNED** | HIGH |
| Transform (axis constraint) | production `RotateTool`/`ScaleTool` (axis param) — **`MoveTool` has none** | Playground (via production tools, no axis) | V1 `constraints.py` + `AxisConstrainedMoveTool` | **UNCLEAR** (partial promotion) | MEDIUM |
| Topology tools | **`playground/topology_tools/*`** | Playground window + tests | V1 `topology_tools`/`loop_ring`/`extrude_tool` | **PLAYGROUND-OWNED (ported, research)** | HIGH |
| Presentation / display | `src/mirai/viewport/display.py` (state) + `playground/experiments/presentation/*` (research) | production + Playground | V1 `display_state.py` | **PRODUCTION + PLAYGROUND split** | HIGH |
| Rendering (draw) | **`playground/window.py`** (live) / `src/viewport` (no draw call) | Playground; Lab has its own | V1 `app.py` draw | **UNCLEAR** *(previously reported)* | HIGH |
| Core→Viewport binding | **two**: Lab `core_to_render.CoreRenderBinding` and Playground `renderer.py`+`app.py` | Lab / Playground respectively | V0.2 experiment | **DUPLICATE, neither authoritative** | HIGH |
| HUD | **`playground/hud.py`** | Playground | Lab (extracted) | **PLAYGROUND-OWNED** | HIGH |
| Window / event loop | **`playground/window.py`** | Playground (manual) | V1 `app.py`, Lab harness | **PLAYGROUND-OWNED (research app)** | HIGH |
| Experiment hosting | **`playground/{experiment,slot}.py`** | Playground | Playground-original (AP-02) | **PLAYGROUND-OWNED** | HIGH |
| Articulation (EX-A) | **`playground/experiments/articulation/articulation.py`** | Playground window + tests | new (EX-A H01) | **PLAYGROUND-OWNED (research)** | HIGH |
| Character research helpers | `experiments/rigging-skinning-morphing/{bone,deformation,rig_controller,inspection,living_mesh_harness}.py` | rigging's own entry points + tests; Playground uses only `Transform` | rigging experiment | **EXPERIMENT-OWNED (active research)** | HIGH |
| Head asset | **`experiments/rigging-skinning-morphing/meshes/head_basemesh.obj`** | rigging + Lab + Playground (3 path constants) | rigging experiment | **EXPERIMENT-OWNED, shared asset** | HIGH |
| OBJ loading | `experiments/rigging-skinning-morphing/loaders/obj_loader.py` | rigging + Lab + Playground | rigging experiment | **EXPERIMENT-OWNED, shared infra** | HIGH |
| History | `src/core/history.py` + `core/operations/topology.MeshStateCommand` | all | Core V1 | **PRODUCTION-OWNED (frozen)** | HIGH |
| Input mapping | `src/mirai/interaction/{input,bindings}.py` (declared) — **no live runtime consumer**; Playground uses `input_map.py` + hardcoded keys | production tests; Playground (its own) | V1 `input_binding`/`default_bindings` | **UNCLEAR** *(previously reported as AI-hostile)* | HIGH |

---

## 7. Lifecycle Map (Q9)

| Component | Origin | Current role | Current consumer | Future direction | Confidence |
|---|---|---|---|---|---|
| `src/core/*` | Core V1 experiment | production domain | all | **KEEP** | HIGH |
| `src/mirai/*` | V1 experiment (promoted) | production application/interaction | production tests, Playground | **KEEP** (some declared-but-unhandled commands) | HIGH |
| `src/viewport/*` | V0.2 experiment (promoted) | production render-data | `Application`, Lab, Playground | **KEEP** | HIGH |
| `playground/*` | own | the live application / research host | artist | **KEEP** | HIGH |
| `playground/experiments/*` | own | variant families | Playground window | **KEEP** (verdicts pending) | HIGH |
| `playground/topology_tools/*` | V1 ports | topology research | Playground | **KEEP** | HIGH |
| `experiments/mirai_bastel_viewport_V1/viewport/*` | own (first viewport) | superseded reference + one launcher's window | rigging `run_viewport.py` | **INVESTIGATE** (port the launcher) → then ARCHIVE | HIGH |
| V1 `tests/*`, `perf/*` | own | regression + perf evidence | V1 | **KEEP** | HIGH |
| V1 `SELECTION_MODES.md`, WP-03 report | own | superseded docs | readers | **ARCHIVE** | MEDIUM |
| `experiments/mirai_bastel_viewport_V02/*` | own | superseded proof | none | **ARCHIVE** | HIGH |
| `experiments/rigging-skinning-morphing/{bone,deformation,rig_controller,inspection,living_mesh_harness}.*` | own | **active research** | rigging entry points + tests | **KEEP** | HIGH |
| `.../deformation.py::Transform` | own | shared rigid-transform primitive | **Playground EX-A** | **EXTRACT** (small) or KEEP as documented contract | HIGH |
| `.../loaders/obj_loader.py` | own | OBJ parser used across areas | rigging, Lab, Playground | **INVESTIGATE** (owner decision) | MEDIUM |
| `.../meshes/head_basemesh.obj` | own | shared asset | rigging, Lab, Playground | **INVESTIGATE** (3 path constants) | MEDIUM |
| `.../run_viewport.py`, `viewport_adapter.py` | own + V1 bridge | manual V1-based viewer | artist, manually | **INVESTIGATE** / **MIGRATE** | HIGH |
| `.../Tests/test_topology_operations.py` | own | **uncollectible** | none | **INVESTIGATE** (report only, don't fix) | HIGH |
| `lab/adapters/obj_to_core.py` | own (port of rigging adapter) | **application infrastructure** | Lab + **Playground** | **EXTRACT** (then Lab may be archived) | HIGH |
| `lab/adapters/{core_to_render,picking,triangulate}.py` | own | Lab-only adapters | Lab harness/tests | **KEEP** while Lab lives / **INVESTIGATE** for `picking` | HIGH |
| `lab/{integration,scene,report,run,_*}.py` | own | Lab harness | Lab | **KEEP** (reference) | HIGH |
| `lab/lab_camera.py` | own | redundant override | Lab | **INVESTIGATE** → ARCHIVE | HIGH |
| `lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md` | own | cited SSOT, stale on camera | docs + comments | **ARCHIVE/annotate** | HIGH |
| `lab/tests/*` | own | green verification | Lab | **KEEP** | HIGH |
| `tests/{mesh,history,operations_init}.py`, `tests/test_extrude_tool.py`, `tests/mnt/**`, `tests/*.patch` | mixed | dead/orphaned | none | **ARCHIVE** (already owner-decided candidates) | HIGH |
| `playground/experiments/articulation/_old_/*` | own | dead duplicate | none | **ARCHIVE** | HIGH |

---

## 8. Candidates for Extraction / Promotion (Q10, Q11)

Only small, reversible items. Each is independent of the others.

### 8.1 — `frame_camera_on_bounds` + `mesh_bounds`/`mesh_center_and_radius`
- **Current location:** `experiments/mirai_bastel_integration_lab/adapters/obj_to_core.py:74-129` (and a fork-typed twin in `rigging/viewport_adapter.py:73-129`).
- **Current consumer:** Lab harness; **`playground/app.py:105` (runtime)**.
- **Proposed permanent owner:** `src/mirai` (it is pure scene/view framing over the public Core query API, exactly like `scene_factory`) — or Playground-local if it must stay experimental.
- **Why:** it is application infrastructure (camera start framing), not research.
- **Smallest extraction:** move the three pure functions (no imports beyond `math`) into one module; `playground/app.py` imports from there. The remaining Lab harness keeps working because it imports the same functions — the Lab harness would then depend on the new owner instead of the reverse.
- **Confidence:** HIGH.

### 8.2 — `build_core_scene_from_obj` / `obj_data_to_core_mesh`
- **Current location:** same file (`obj_to_core.py:40-66`).
- **Current consumer:** Lab `scene_objects`; **`playground/app.py:135` (runtime)**.
- **Proposed permanent owner:** `src/mirai/scene_factory.py` (scene construction already lives there) — the natural companion to `create_cube`/`build_cube_scene`.
- **Why:** "OBJ → Scene" is scene construction, and `scene_factory` is already the production home for the cube equivalent.
- **Smallest extraction:** move the 2 functions; they depend only on `core.mesh`, `core.scene`, and `load_obj`. Note this **does not** remove the rigging dependency (the loader stays in rigging) unless the loader is also given a home.
- **Confidence:** MEDIUM-HIGH (the "load_obj" question is a prerequisite — see Open Questions).

### 8.3 — `Transform` rigid-transform primitive
- **Current location:** `experiments/rigging-skinning-morphing/deformation.py` (imports only `__future__`, `typing`).
- **Current consumer:** `playground/experiments/articulation/articulation.py:42`.
- **Proposed permanent owner:** Playground-local, or a small `src` math/transform utility.
- **Why:** it is ~40 lines of pure math with zero research semantics; the Playground already documents *why* it reuses it.
- **Smallest extraction:** either vendor `Transform` (translation + 3×3 rotation + `apply`) beside `articulation.py`, or promote it as a documented shared primitive. Either way the rigging experiment is unaffected.
- **Confidence:** HIGH (smallest leak in the repository).

### 8.4 — Port `rigging/run_viewport.py` off V1
- **Current location:** `run_viewport.py:29-47` (V1 window classes) + `viewport_adapter.py:36-43` (fork).
- **Current consumer:** manual launches only.
- **Proposed permanent owner:** a harness on `src/viewport` (or the Playground host).
- **Why:** this is the *only* thing keeping V1's viewport package alive.
- **Smallest extraction:** rewrite the ~10-line window subclass against a production-core harness, and align `viewport_adapter` from `mirai_bastel_core` to `src.core`. Crucially, the adapter's helper logic is **already** available in its production-core form in the Lab's `obj_to_core.py` — so the work is a re-target, not a re-write.
- **Blocker (capability, not code):** V1's `AllToolsWindow` offers axis-constrained Move and a Scene-accepting constructor; the Playground offers neither. So this candidate has a genuine open question attached (§10).
- **Confidence:** MEDIUM (technically small, but requires a product/architecture decision).

### 8.5 — Collapse three head-asset path constants to one
- **Current locations:** `lab/_paths.py:40`, `rigging/viewport_adapter.py:48`, `playground/_paths.py:45`.
- **Current consumers:** Lab, rigging, Playground.
- **Proposed permanent owner:** whichever side the ownership decision names (§10).
- **Smallest extraction:** one constant referenced by the others; no code move required.
- **Confidence:** HIGH (trivial, but only worthwhile *after* the owner decision).

### 8.6 — Lab `adapters/picking.py`
- **Current location:** `lab/adapters/picking.py:27-51` (delegation to production + a duplicated 14 px threshold constant).
- **Current consumer:** `integration/lab_viewport.py:49`.
- **Proposed permanent owner:** production already owns it; the shim has no reason to survive a Lab archive.
- **Smallest extraction:** the harness can call `mirai.viewport.picking.pick_nearest_vertex` directly.
- **Confidence:** HIGH (only relevant if/when the Lab is archived — not before).

**Explicit non-candidates (deliberately *not* proposed):** merging the two draw paths, unifying the Lab's `CoreRenderBinding` with `PlaygroundRenderer`, unifying `viewport_adapter` with `obj_to_core`, merging the four cube builders, deleting `adapters/triangulate.py`, or moving any directory for cleanliness.

---

## 9. Things That Should NOT Be Touched

**Historical evidence / reference implementations**
1. `experiments/mirai_bastel_core_V1/mirai_bastel_core/*` — a live dependency of both V1 and rigging, and the frozen reference state.
2. `experiments/mirai_bastel_viewport_V1/viewport/*` — **until** `run_viewport.py` is ported; deleting or renaming the package breaks a live manual path.
3. `experiments/mirai_bastel_viewport_V1/tests/*` — 184 green tests; the regression evidence for the first interactive viewport.
4. `experiments/mirai_bastel_viewport_V02/*` — the V0.2 proof and its recorded results.

**Performance / measurement material**
5. `experiments/mirai_bastel_viewport_V1/perf/*` (6 scripts + 4 result files + `PERF_BASELINE_REPORT.md`) — the only pre-V0.2 performance evidence; "old" is irrelevant here, benchmarks are permanent evidence.

**Active research**
6. `experiments/rigging-skinning-morphing/{bone,deformation,rig_controller,inspection,living_mesh_harness}.py` + `run_living_mesh.py` + `run_topology_survival_research.py` + `Tests/*` — active track referenced by `CHARACTER_SYSTEMS_RESEARCH.md` and EX-A.
7. `experiments/rigging-skinning-morphing/meshes/*` — the head asset is used by the live Playground; `.blend` is provenance.
8. `playground/experiments/*` + `decision.md` + `tweak_decision.md` — open verdicts; cleanup would destroy the experiment.
9. `playground/topology_tools/*` + `playground/topology_ops.py` — ported, tested, keyed, in active use.
10. `experiments/topology/TOPOLOGY_EXPERIMENT_PLAN.md` — already current and Playground-aware.

**Still-used runtime infrastructure**
11. `lab/adapters/obj_to_core.py` + `lab/_paths.py` — the Playground imports them; the Lab directory must stay on `sys.path` for now.
12. `rigging/loaders/obj_loader.py` — shared parser, used transitively by the live Playground.
13. `playground/_paths.py` — its `sys.path` ordering is load-bearing (comment: `src/` before repo root).
14. `src/*` — no experiment coupling exists; nothing to detangle.

**Regression / verification material**
15. `lab/tests/*` (52 green) and `experiments/rigging-skinning-morphing/Tests/*` (92 green, minus the uncollectible file).
16. `lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md` — preserve as historical evidence even though §A.1 is stale; annotate, don't rewrite (AGENTS.md §6: do not edit an archived review to agree with a later decision).

**Deliberately *not* touched despite looking obsolete**
17. `lab/adapters/triangulate.py` — an intentional research alternative, explicitly excluded from the production path.
18. `lab/integration/lab_viewport.py` — the minimal reference harness; it is also the only place that has ever exercised the production viewport on real GL (its `--selftest` + pixel probe).
19. `lab/lab_camera.py` and `playground/camera.py` overrides — redundant, but they are documented findings and carry their own regression tests (`playground/tests/test_playground_camera.py`); removal is a decision, not a cleanup.
20. `tests/*` production suite — 398 green; unchanged by anything above.

---

## 10. Open Questions

Only questions that require an architectural or artistic decision:

**Q-A — Does the rigging experiment still need a *visual* workbench at all?**
Its research entry points are headless (`run_living_mesh.py`: *"without viewport"*), and `run_viewport.py` does not even apply deformation to what it shows — it loads the head and enables V1's tools. Is "look at the head and hand-edit it inside V1" still a needed step in the rigging workflow, or is it now superseded by the Playground's `H` (head) + topology tools? *This single answer decides V1's fate.*

**Q-B — If yes, which harness should show it?**
V1's `AllToolsWindow` accepts an external Scene and offers axis-constrained Move; the Playground offers neither but has selection variants, tweak, topology, articulation and history-consistent transforms. Choose: (a) port the launcher to a production-core harness, (b) make the Playground accept an external Scene, or (c) keep V1 deliberately as the rigging viewer.

**Q-C — Who owns the head basemesh asset?**
Is `head_basemesh.obj` research data belonging to the rigging experiment, application/test data belonging to the Playground, or shared data that deserves a neutral location? (Today: 3 path constants point at it.)

**Q-D — Who owns the OBJ loader?**
`loaders/obj_loader.py` is infrastructure (a pure parser) living inside a research experiment, used by three areas. Keep as rigging-owned with a documented contract, or give it a permanent home?

**Q-E — Is OBJ→Scene + camera framing a production capability or a Playground convenience?**
`build_core_scene_from_obj` + `frame_camera_on_bounds` are sequence-independent of experiments but currently live in the Lab. Promote to `src/mirai/scene_factory` (production) or keep them Playground-local?

**Q-F — Is axis-constrained Move part of the production transform semantics?**
`RotateTool`/`ScaleTool` accept `axis=`; `MoveTool` does not. V1's `AxisConstrainedMoveTool` was V1-local. Was that a deliberate scope decision for WP-03, or an unfinished promotion?

**Q-G — Is the Integration Lab's "would-be application" role closed?**
Its README describes an integration test studio; the Playground took the application role. Is the Lab now (a) a minimal reference harness worth maintaining, (b) primarily a source of helpers, or (c) a completed experiment to be archived after extraction?

**Q-H — Does the Playground owe a "history-consistent transform" contract to the rigging viewer?**
The Lab's harness explicitly moves vertices *without* history ("documentierter Folgeschritt"); the Playground's transforms push exactly one `MeshStateCommand`. If a rigging viewer ever needed editing, which semantics apply?

**Q-I — Who owns the "Core → production Viewport" binding?** *(carried over from the previous audit)*
Two live implementations exist (Lab `CoreRenderBinding`, Playground `renderer.py`+`app.py`) with different completeness. Which is the reference?

---

## 11. Suggested Investigation Order

No implementation plan — only the order in which the decisions above should be made.

1. **Decide Q-A:** is the rigging experiment's V1 viewer still needed? (Everything else about V1 depends on this.)
2. **If yes, narrow Q-B:** enumerate the exact capabilities the viewer needs (external Scene acceptance, axis-constrained Move, topology tool set) and confirm which of them the Playground lacks.
3. **Decide the permanent owner for those capabilities** (V1 stays, production harness, or Playground host). Only then does V1's archive status become decidable.
4. **Decide Q-C and Q-D** — asset and loader ownership. Both are small but they gate every "extract the helper" move, because the Playground's head path is `helper → loader → asset`.
5. **Decide Q-E** — permanent home for OBJ→Scene + framing. This is the smallest dependency-removal that touches the live application.
6. **Then extract only what was decided in (3)–(5)** — one item at a time, re-running the Playground suite (233 tests) and the Lab suite (52 tests) after each.
7. **Re-audit dependencies** (a single repeated grep for `adapters|loaders|mirai_bastel_core|deformation` outside `experiments/`) to confirm what the Playground still borrows.
8. **Decide Q-G** — whether the Lab remains a maintained harness. Only after (6)–(7) can an archive decision be made without breaking the live application.
9. **Decide Q-F and Q-I** last — both are production-architecture questions (transform semantics; viewport binding ownership) that do not block steps 1–8.
10. **Only after all of the above:** consider archiving `mirai_bastel_viewport_V02`, the Lab's stale audit, the redundant camera overrides, and the previously reported dead/orphaned files — each as its own documented decision.

---

### Summary of what exists, who uses it, and why

| Layer | Status today |
|---|---|
| `src/` | Production. Immaculate dependency direction: **no production module imports any experiment.** |
| `playground/` | The live application and research host. Borrows 3 small capabilities + 1 asset from two experiments. Depends on no experiment as a system. |
| `experiments/mirai_bastel_integration_lab/` | **Dependency container + live helper (`obj_to_core`) + Lab-only harness (466 L) + Lab-only adapters + 52 green tests.** Not one thing — several. |
| `experiments/rigging-skinning-morphing/` | **Active research** (headless, green) + **the last V1 consumer** (one manual GL launcher) + 2 shared infrastructure assets (loader, head). |
| `experiments/mirai_bastel_viewport_V1/` | Superseded reference implementation, green (184 tests), perf evidence, **one remaining external consumer (a manual window)**. |
| `experiments/mirai_bastel_viewport_V02/` | Fully superseded; nothing imports it. |

**Repository unchanged:** `git status --short` is empty; HEAD is `b3f7344`. No files were created, edited, renamed, moved or deleted, and no commits or branch changes were made.