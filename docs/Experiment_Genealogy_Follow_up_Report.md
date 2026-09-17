I have the full evidence now. Note one repository-reality update since the previous audit: HEAD is now `5701563` *"Repo_Audit"* (2026-09-17), which added `docs/Repository_Wide Structural_Codebase_Health_Audit.md` (the previous report). Worktree is clean; I made no changes.

---

# Experiment Genealogy — Follow-up Report

## Executive Summary

The artist's observation is **factually correct in direction, but the conclusion "old experiments may be obsolete" does not hold** for two of the six areas.

Real, verified findings:

1. **`src/` (production) has zero imports into `experiments/`.** Verified by recursive grep across every `.py` file: no production module resolves to any experiment. The documented dependency direction holds.
2. **`playground/` (the only runnable application) depends on two experiments at runtime**, not on V1:
   - `experiments/mirai_bastel_integration_lab` → `adapters.obj_to_core.build_core_scene_from_obj`, `frame_camera_on_bounds`, `DEFAULT_HEAD_ASSET`
   - `experiments/rigging-skinning-morphing` → `deformation.Transform` (articulation), `loaders/obj_loader`, head asset
3. **`mirai_bastel_viewport_V1` is *not* imported by production, playground or the production test suite** — but it is **still imported by exactly one consumer**: `experiments/rigging-skinning-morphing/run_viewport.py`, together with the `mirai_bastel_core` fork.
4. **V1 still runs and is still green:** its complete headless test suite is `184 passed, 21 subtests passed` — run for this audit. "Old" ≠ "dead" ≠ "broken" applies here precisely.
5. **V1 is the ancestor of large parts of `src/mirai` and `playground/topology_tools`.** The migration already happened; what remains in V1 is the *original*, the *perf research*, the *axis-constraint experiment*, and the *only GL harness for the Core-V1 fork*.
6. **The "experiments/ vs playground/experiments/" distinction is documented in two separate vocabularies that never reference each other**, and the AI onboarding file (`CLAUDE.md`) does not mention `playground/` at all.
7. **A historic namespace hazard was caused by a stray 1-line file** at the repo root (`viewport/extrude_tool.py`, content: `<longcat_arg_value>`, created 2026-09-03, deleted 2026-09-11). The file is gone; three defensive workarounds and their comments remain.

No cleanup is warranted on this evidence. Several *documentation* statements are demonstrably stale, and exactly one code path (rigging → V1) is the remaining thread that keeps V1 alive.

---

## Experiment Genealogy

### 1. `experiments/mirai_bastel_core_V1/`

| | |
|---|---|
| **Original role** | First Core validation milestone; frozen reference state of the Core experiment (2026-08-25/26, commits `37a97b1`, `348cdf2`, `4b18327`). |
| **Current role** | Reference/archive copy **and** load-bearing dependency of the V1 viewport experiment and of the rigging experiment. |
| **Current dependencies** | Imported as `mirai_bastel_core` by: all of `experiments/mirai_bastel_viewport_V1/viewport/*` (e.g. `all_tools_app.py:42`, `topology_tools.py:7`, `transform_tool.py:50`), all 15 V1 test files, `V1/perf/*`, and `experiments/rigging-skinning-morphing/viewport_adapter.py:43` + `Tests/test_viewport_integration.py:35`. **Nothing outside the experiment area imports it** except `tests/test_extrude_tool.py:19`, which is broken and excluded from the documented run. |
| **Survived elsewhere** | Entirely — `src/core/*` is the promoted production baseline (verified: `src/core` imports contain no experiment references). |
| **Classification** | **HISTORICAL / ARCHIVE** (as project memory) **+ CURRENT DEPENDENCY** (indirect, via V1 and rigging) **+ SOURCE OF CURRENT IMPLEMENTATION** (`src/core`). |
| **Confidence** | HIGH. |

Note: `mirai_bastel_core/move.py` exists *beside* `mirai_bastel_core/operations/move.py` — the analogous orphan in production (`src/core/move.py`) was deleted in `bbeef97`; the experiment copy retains the duplication. (Also flagged in my previous audit.)

### 2. `experiments/mirai_bastel_viewport_V1/` — see dedicated deep dive below

| | |
|---|---|
| **Original role** | The first interactive GL viewport, built to prove the pipeline `Scene → Mesh → Selection → Operation → Commit → History → Undo/Redo` against the frozen Core (2026-08-26). Later grew a Topology Lab and an All-Tools Playground. |
| **Current role** | Green, self-contained reference implementation **plus** the viewport of the rigging experiment. |
| **Current dependencies** | → `mirai_bastel_core` (Core-V1 fork) only. Imported by `experiments/rigging-skinning-morphing/run_viewport.py:29-47`. Not imported by `src/`, `playground/`, or `tests/`. |
| **Survived elsewhere** | See the survival table in the deep dive. |
| **Classification** | **SOURCE OF CURRENT IMPLEMENTATION** + **CURRENT DEPENDENCY** (exactly one) + **SUPERSEDED** (its interactive role was taken over by `playground/`). Not "purely historical". |
| **Confidence** | HIGH. |

### 3. `experiments/mirai_bastel_viewport_V02/`

| | |
|---|---|
| **Original role** | Proof-of-Architecture for incremental update ("update only what changed"); documented 10/10 tests + GPU live check. |
| **Current role** | Superseded. Declared `⚫ OUT` in `ARCHITECTURE_MAP.md`. Nothing imports it (recursive grep: only *docstring references from `src/viewport/*`* as its origin). |
| **Survived elsewhere** | Fully — `src/viewport/{category,derived,render_mesh,overlay,resource_store,benchmark}.py` name-drop it as the source of the promoted architecture. |
| **Classification** | **SUPERSEDED** / **HISTORICAL**. |
| **Confidence** | HIGH. |

### 4. `experiments/mirai_bastel_integration_lab/`

| | |
|---|---|
| **Original role** | Integration harness / test studio (fixed cube + head scene), written before Gate 3 existed. |
| **Current role** | Production-based since WP-IL-01 (2026-09-08) — imports `src/mirai/viewport/camera.py` and `src/viewport`; **and it is a load-bearing helper library for the Playground**. |
| **Current dependencies** | → `src/` (production), → `loaders` (rigging), → `mirai_bastel_viewport_V02` *no longer* (README: "das V0.2-Experiment wird nicht mehr importiert"). Imported by `playground/app.py:27-30` and by `playground/tests/test_playground_camera.py:25` (adds the lab dir to `sys.path`). |
| **Survived elsewhere** | Its adapter pattern; its `obj_to_core` OBJ→Scene path is now *the* Playground startup path. Its `lab_camera.py` view-matrix override is redundant (production camera was fixed in `bbeef97`) — carried over from the previous audit. |
| **Classification** | **CURRENT DEPENDENCY** (framing/OBJ/head asset) + **ISOLATED PROTOTYPE** (the window harness itself). |
| **Confidence** | HIGH. |

### 5. `experiments/rigging-skinning-morphing/`

| | |
|---|---|
| **Original role** | Research: rigging/skinning/morphing combined with topology editing; later "Living Mesh" + topology-survival research. |
| **Current role** | **ACTIVE RESEARCH** (separate track, `docs/research/CHARACTER_SYSTEMS_RESEARCH.md`, EX-A) **and the last consumer of the V1 viewport + Core-V1 fork**. |
| **Current dependencies** | → `mirai_bastel_core` (via `viewport_adapter.py`), → V1 viewport package (via `run_viewport.py`), → `src/core` (its own modules: `demo_mesh.py`, `inspection.py`, `living_mesh_harness.py`: `from src.core.mesh import Mesh`). Imported by `playground/experiments/articulation/articulation.py` (`from deformation import Transform`) and by Playground tests. |
| **Survived elsewhere** | OBJ loader + head basemesh (now used by the Playground through *two different* adapters: the lab's and this one's); `deformation.Transform` used by EX-A articulation. |
| **Test reality (run for this audit)** | `test_viewport_integration.py` + `test_obj_loader.py` → **28 passed**; `test_living_mesh.py` + `test_mutation_sequences.py` + `test_rig_controller.py` → **64 passed**; `test_topology_operations.py` (6 tests) → **uncollectible**: `@pytest.fixture(skipif=..., reason=...)` at lines 37 and 64 (invalid pytest API). |
| **Classification** | **ACTIVE RESEARCH** + **CURRENT DEPENDENCY** (of Playground) + **partially rotted test infrastructure**. |
| **Confidence** | HIGH. |

### 6. `experiments/topology/`

| | |
|---|---|
| **Original role** | Documentation + plan home for topology research (code lived in V1). |
| **Current role** | Documentation only. |
| **Current dependencies** | None (no Python). |
| **Survived elsewhere** | Its Phase 1–3 findings were implemented in `playground/topology_tools/` + `playground/window.py` (keys K/I/J/G/E) and **already documented inside `TOPOLOGY_EXPERIMENT_PLAN.md:151-153`** (it names `playground/topology_tools/connect_edges.py`, `playground/window.py` key **J**, and `playground/tests/test_topology_connect_edges.py`). |
| **Classification** | **ACTIVE RESEARCH** (the plan file) / **stale summary** (the README phase status). |
| **Confidence** | HIGH. |

---

## Dependency Map

Real, code-level directions only (verified by recursive grep):

```text
PRODUCTION
  src/core  ◄──  src/mirai  ◄──  src/viewport
      ▲            ▲                ▲
      │            │                │
      │        (nothing in experiments/ imports into src/ ... )
      │
      └── src/  ──X──►  experiments/            ✅ verified: no production→experiment import

PLAYGROUND  (the only runnable application)
  playground/  ──►  src/{core,mirai,viewport}
       │
       │ sys.path +=  experiments/mirai_bastel_integration_lab
       │               experiments/rigging-skinning-morphing
       │               src/  (before repo root)
       ▼
  playground/app.py ──► adapters.obj_to_core        (INTEGRATION LAB)   ← load-bearing
  playground/experiments/articulation/articulation.py ──► deformation   (RIGGING) ← load-bearing
  playground/experiments/articulation/demo_cylinder.py ──► core.mesh    (own build, not a port)
  playground/topology_tools/*  ──► textual ports from V1 (docstring only, NO import)
  playground/_paths.py does NOT add V1 to sys.path

PRODUCTION TESTS
  tests/test_playground_transformer.py ──► playground ──► lab + rigging
  tests/test_extrude_tool.py ──► mirai_bastel_core + viewport.extrude_tool   [BROKEN; excluded]
  tests/{test_camera,test_input_binding,test_tool_lifecycle}.py  ← "Migriert aus V1/tests/..."

EXPERIMENT → EXPERIMENT
  rigging:run_viewport.py ──► experiments/mirai_bastel_viewport_V1/viewport/{all_tools_app,topology_app}
  rigging:viewport_adapter.py ──► mirai_bastel_core   (experiments/mirai_bastel_core_V1)
  V1:  viewport/* and tests/* and perf/* ──► mirai_bastel_core
  V1  ──X──►  production                        (V1 never imports src/)
  lab ──► src/ (production) + loaders (rigging)
```

**The only "looks historical but is load-bearing" cases are:**
1. `experiments/mirai_bastel_viewport_V1` → rigging `run_viewport.py` (single, live, documented, *unported*).
2. `experiments/mirai_bastel_core_V1` → rigging `viewport_adapter.py` + V1 (the fork is deliberately kept: *"ein Angleich ist eine spätere, bewusste Entscheidung"*).
3. `experiments/mirai_bastel_integration_lab/adapters/obj_to_core.py` → Playground startup **and** head asset.
4. `experiments/rigging-skinning-morphing/deformation.py` → Playground articulation (EX-A).

---

## Viewport V1 Deep Dive

**Is V1 still used?**
Yes — but by exactly one runtime consumer: `experiments/rigging-skinning-morphing/run_viewport.py` (adds `experiments/mirai_bastel_viewport_V1` to `sys.path`, imports `viewport.all_tools_app.AllToolsWindow` and `viewport.topology_app.TopologyWindow`, subclasses them for the head-basemesh scene). It is **not** used by `src/`, `playground/`, or the production test suite.

**What imports it (complete list):**
| Importer | Kind |
|---|---|
| `experiments/rigging-skinning-morphing/run_viewport.py:29-47` | **live runtime import** |
| `playground/topology_tools/{connect_edges,loop_ring}.py:3`, `extrude.py:87`, `playground/topology_ops.py:6` | docstring references only ("1:1-Logik-Port…") |
| `tests/{test_camera,test_input_binding,test_tool_lifecycle}.py:3` | docstring references only ("Migriert aus…") |
| `tests/test_extrude_tool.py:17-19` | broken path (`repo/../mirai_bastel_core_V1`), excluded from documented run |
| V1's own entry points (`run.py`, `run_topology.py`, `run_cylinder.py`, `run_all_tools.py`, `_smoke_*.py`, `perf/*`) | self |

**What from V1 survived elsewhere:**

| V1 module | Now lives as | Kind |
|---|---|---|
| `viewport/vecmath.py` | `src/mirai/viewport/vecmath.py` | promoted |
| `viewport/camera.py` | `src/mirai/viewport/camera.py` | promoted |
| `viewport/picking.py` | `src/mirai/viewport/picking.py` | promoted |
| `viewport/display_state.py` | `src/mirai/viewport/display.py` | promoted |
| `viewport/commands.py` | `src/mirai/interaction/commands.py` | promoted |
| `viewport/input_binding.py` | `src/mirai/interaction/input.py` | promoted |
| `viewport/default_bindings.py` | `src/mirai/interaction/bindings.py` | promoted |
| `viewport/tool.py` | `src/mirai/interaction/tool.py` (+ `tool_manager.py`) | promoted |
| `viewport/move_tool.py` | `src/mirai/interaction/tools/move.py` | promoted |
| `viewport/transform_tool.py` | `src/mirai/interaction/tools/{transform,rotate,scale}.py` | promoted |
| `viewport/app.py` | `src/mirai/application.py` (window-free extraction, Gate 3) | promoted in parts |
| `tests/test_camera_picking.py`, `tests/test_input_binding.py`, `tests/test_tool_lifecycle.py` | `tests/test_camera.py`, `tests/test_input_binding.py`, `tests/test_tool_lifecycle.py` | promoted (docstrings say "Migriert aus…") |
| `viewport/topology_tools.py` | `playground/topology_tools/connect_edges.py` | ported (documented) |
| `viewport/loop_ring.py` | `playground/topology_tools/loop_ring.py` | ported (documented) |
| `viewport/extrude_tool.py` | `playground/topology_tools/extrude.py` | adapted (documented) |
| `viewport/constraints.py` | **only partially** — `src/mirai/interaction/tools/rotate.py` has `axis=`/pivot constraints; **production Move has no axis constraint** (`src/mirai/interaction/tools/move.py` has no `axis`) | concept partly promoted, module not |
| `viewport/all_tools_app.py::AxisConstrainedMoveTool` | nothing | not migrated (V1-only experiment) |
| `viewport/topology_scene_cylinder.py` (open cylinder) | `playground/experiments/articulation/demo_cylinder.py` is an **independent new build** (capped cylinder, Y axis, `core.mesh`, EX-A rationale) — similar idea, not a port | convergent, not duplicate |
| `viewport/demo_scene.py`, `topology_scene.py`, `topology_app.py`, `app.py` window, `_smoke_*.py` | nothing | V1-only harness/scenes |
| `perf/*` (incl. `PERF_BASELINE_REPORT.md`, 4 result files) | nothing | research evidence, never migrated |
| `keymap.json` (referenced by README/app.py) | not present in the repository | documented-but-absent optional overlay |

**Is it safe to regard V1 as historical?**
**No — not completely.** Two things keep it current:
1. one live runtime consumer (rigging `run_viewport.py`),
2. its role as the *ancestor reference* for promoted code (which is legitimate project memory per M1).

Everything else about it is superseded. Its test suite is fully green today (**184 passed + 21 subtests**, all headless — even the three "pyglet" test files stub the window: `_HeadlessAllToolsWindow`), so it is not rotted, merely out of role.

**Unresolved dependencies:**
- `run_viewport.py` → V1 viewport package (the remaining blocker for calling V1 purely historical).
- `viewport_adapter.py` → `mirai_bastel_core` fork, with an explicit "alignment is a later, deliberate decision" note.
- `experiments/mirai_bastel_viewport_V1/requirements.txt` pins `pyglet>=2.0,<3.0` — a second, experiment-local dependency declaration next to the (nonexistent) repo-level one.
- The **package-name collision**: V1 declares `viewport/__init__.py` *specifically* so the experiment package cannot be silently merged with another `viewport/` earlier on `sys.path` (its docstring says so verbatim). That collision is real today whenever multiple bootstraps run together — it is the direct cause of the 46 collection errors under bare `pytest` documented in the previous audit.

---

## Top-Level `experiments/` vs `playground/experiments/`

**How they are actually different:**

| | `experiments/` | `playground/experiments/` |
|---|---|---|
| Unit | A **project area** (one directory = one research program with its own README, tests, entry points, sometimes its own Core fork) | A **variant family inside one host** (`<family>/variant_*.py` + `decision.md`) |
| Lifecycle | May be pragmatic, disposable, may pin its own dependencies, may fork the Core | Registered as `VariantEntry` in an `ExperimentSlot`; `activate/deactivate/update/draw` contract (`playground/experiment.py`) |
| Verdict apparatus | none (findings go to docs) | `Decision` KEEP/ITERATE/REJECT + `decision.md` generation (`playground/slot.py`) |
| Runtime | started manually, own entry points | reachable at runtime via Tab/family cycling in one window |
| Promotion | "architecture decision → `src/`" | "Artist verdict → candidate → production review" |

**Is the distinction documented?** Yes, but in **two documents that never reference each other**:
- `playground/experiments/` is defined by `docs/design/artist_playground/EXPERIMENT_HOST.md` (§3 terminology, §16 interaction grammar) and `playground/slot.py:12-15` (file convention).
- `experiments/` is defined by `experiments/README.md` ("Kleine technische Experimente und Praxistests … bevor daraus Produktionscode unter `src/` wird"), `AGENTS.md §7`, `CLAUDE.md`.

**Neither index mentions the other.** `experiments/README.md` contains **zero** mentions of the Artist Playground; `CLAUDE.md` contains **zero** mentions of `playground/` at all (its "Structure" list is `src/core`, `src/viewport+mirai`, `experiments/`, `tests/`, `docs/`, `references/`).

**Are we effectively migrating active research from `experiments/` into `playground/experiments/`?**
Yes — and the repository already shows the two-stage pattern for exactly one topic:
1. Topology: V1 experiment → `playground/topology_tools/` (ported, tested, keyed) — **migrated**.
2. Selection: V1 `SELECTION_MODES.md` ("current selection experiment reference") → `playground/selector.py` + 3 variants — **migrated, but the old document still calls itself "current"** (see drift D2).
3. Tweak / Presentation / Transform-activation: **never existed in V1 at all** — born directly in the Playground. So it is not a pure migration; the Playground also *generates* new research.
4. Cylinder test body: **independently rebuilt**, not migrated.

So the movement is real but partial and topic-dependent — which is why a blanket "old experiments are obsolete" conclusion would be wrong, and an equally blanket "everything must be migrated" would be wrong too.

---

## Architecture Drift Findings

**D1 — `experiments/topology/README.md` phase status is two phases behind its own sibling plan** *(HIGH)*
Lines 77/79/85 still say *"Noch offen: Loop Insert (Phase 4)"*, *"Phase 4 — Loop Insert / Loop Remove: geplant"*, *"Phase 5 — Extrude: geplant"*. Meanwhile `playground/topology_tools/loop_insert.py`, `loop_slide.py` and `extrude.py` exist and are keyed (`I`, `G`, `E`) in `playground/window.py`, and **`TOPOLOGY_EXPERIMENT_PLAN.md:151-153` already names the Playground files by path, including key `J`**. Same directory: one document current, the other stale.
*Impact:* exactly the failure mode the project already guards against (declaring an implemented capability "missing").

**D2 — V1 is still described as the active research field for selection/topology** *(HIGH)*
`experiments/README.md` (V1 section) calls it *"Aktives interaktives Forschungs- und Praxistestfeld"*; `experiments/mirai_bastel_viewport_V1/SELECTION_MODES.md` calls itself *"the current selection experiment reference"*; `experiments/topology/README.md:5` says the topology code *"liegt derzeit bewusst unter experiments/mirai_bastel_viewport_V1/viewport/"*. In reality the active fields are `playground/` (selection, transform, tweak, topology, articulation) and the V1 code is the *reference* plus one consumer.

**D3 — The AI onboarding quick-reference does not know the Playground exists** *(HIGH)*
`CLAUDE.md` structure list omits `playground/` entirely; `experiments/README.md` does not mention it either. An agent following `CLAUDE.md` gets the impression the research area is `experiments/` and that no interactive application exists. This is the single highest-leverage documentation gap for the question asked here.

**D4 — `experiments/rigging-skinning-morphing/Tests/test_topology_operations.py` cannot be collected** *(HIGH, verified)*
`@pytest.fixture(skipif=not CORE_AVAILABLE, reason=...)` at lines 37 and 64 — `TypeError: fixture() got an unexpected keyword argument 'skipif'`. 6 tests affected. The rest of that experiment's suite runs green (92 passed across 5 files).

**D5 — Historic `viewport` namespace hazard: cause identified, workarounds remain, hazard still latent** *(HIGH)*
`git show 003370f` added `viewport/extrude_tool.py` containing exactly one line: `<longcat_arg_value>` (a tool-call artifact). `git show 0a75005` deleted it and added `experiments/mirai_bastel_viewport_V1/viewport/__init__.py` as a defence. Three comments still describe a "stray top-level `viewport/`" that no longer exists: `playground/_paths.py:15-17`, `tests/_bootstrap.py:11`, V1's `viewport/__init__.py:8-14`. The *real* remaining collision is the duplicate package name `viewport` (V1 vs `src/viewport`), which is what breaks bare `pytest` (46 errors).

**D6 — V1 README documents a `keymap.json` that is not in the repository** *(LOW)*
`requirements.txt` is tracked (`pyglet>=2.0,<3.0`); `keymap.json` is not, though README/`app.py` describe it as an optional user overlay.

**D7 — V1's `constraints.py` concept is only half-promoted** *(MEDIUM)*
`vector/constraints.py` (Constraint enum + hotkey map) has no production counterpart; production `RotateTool`/`ScaleTool` accept `axis=`, but production `MoveTool` has no axis parameter (`src/mirai/interaction/tools/move.py` — verified). V1's `AxisConstrainedMoveTool` was V1-local. So "axis-constrained move" is a realised idea in one code path, unrealised in another, with no owner document saying which is intended.

**D8 — Positive finding (no drift): production has no experiment dependency** *(HIGH)*
Recursive grep over all `.py` files: `src/**` never imports `experiments`, `mirai_bastel_core`, or V1. The coupling is one-directional (`experiments → src`, `playground → experiments`). The architecture boundary is intact even though V1 is still alive for another experiment.

---

## Candidate Future Actions

*(Listed only. No recommendation is implied, and none of these is to be implemented now.)*

**Clarify documentation (no code impact)**
- `experiments/README.md`: restate V1's status as *"reference implementation; interactive role taken over by `playground/`; one remaining consumer: rigging `run_viewport.py`"*; add a paragraph that names `playground/` and distinguishes it from `experiments/`.
- `experiments/topology/README.md`: bring the Phase 4/5 status lines in line with `TOPOLOGY_EXPERIMENT_PLAN.md` and the existing `playground/topology_tools/`.
- `experiments/mirai_bastel_viewport_V1/SELECTION_MODES.md`: mark as historical, point to `playground/selector.py` + `decision.md`.
- `CLAUDE.md`: add `playground/` to the structure list (it is the runnable application).
- `playground/_paths.py`, `tests/_bootstrap.py`, V1 `viewport/__init__.py`: the "stray top-level viewport/" comments refer to a deleted file; the *remaining* hazard is the duplicate package name.

**Remove a dependency (needs a decision, not just work)**
- Port `experiments/rigging-skinning-morphing/run_viewport.py` from the V1 viewport to `src/viewport`/a Playground host. This is the only action that would make V1 purely historical — and it implies aligning the rigging experiment with `src/core` instead of the `mirai_bastel_core` fork (`viewport_adapter.py:17-22` explicitly defers this).

**Migrate remaining helpers**
- Give `adapters.obj_to_core.build_core_scene_from_obj` + `frame_camera_on_bounds` + the head asset a non-experiment home (or a Playground-local copy), since they are Playground startup dependencies.

**Rename (removes a systemic hazard)**
- Rename the V1 package `viewport` (e.g. `viewport_v1`) — prerequisite for any single repo-wide test command.

**Repair or retire**
- `tests/test_extrude_tool.py` (broken imports; duplicates V1's test).
- `experiments/rigging-skinning-morphing/Tests/test_topology_operations.py` (invalid `pytest.fixture(skipif=…)`).

**Archive**
- `experiments/mirai_bastel_viewport_V02` — declare archive explicitly (nothing imports it; already `⚫ OUT`).
- `experiments/mirai_bastel_core_V1` — keep as archive, but record that it is *also* a live dependency of two experiments (so "archive" is not read as "safe to drop").

**Leave intentionally untouched**
- V1 code, tests, `perf/` evidence.
- All pending `decision.md` / `tweak_decision.md` verdict documents.
- `TOPOLOGY_EXPERIMENT_PLAN.md`.
- `experiments/topology/README.md`'s research questions (only its status lines are stale).

---

## What Should NOT Be Touched Yet

1. **`experiments/mirai_bastel_viewport_V1/viewport/*` and its tests** — green (184 + 21 subtests) and the sole viewport of the rigging experiment. Removing or renaming the package before `run_viewport.py` is ported breaks a live research path.
2. **`experiments/mirai_bastel_core_V1/mirai_bastel_core/*`** — a live dependency of both V1 and rigging, not just an archive copy.
3. **`experiments/mirai_bastel_integration_lab/adapters/obj_to_core.py`, `_paths.py`, `scene/`** — load-bearing for the Playground's startup path and head asset.
4. **`experiments/rigging-skinning-morphing/{deformation.py, loaders/obj_loader.py, meshes/head_basemesh.obj}`** — load-bearing for the Playground (articulation) and for the head scene.
5. **`playground/topology_tools/*`, `playground/selector.py`, `playground/experiments/*` and the decision documents** — the active research surface with open verdicts; "cleanup" here would destroy the experiment.
6. **`src/` in any form** — no experiment coupling exists; there is nothing to detangle here.
7. **`experiments/topology/TOPOLOGY_EXPERIMENT_PLAN.md`** — it is already correct and is the one document in that area that tracks the Playground.
8. **The `constraints.py` question** — do not "restore" it or extend it; axis-constrained *Move* is an unresolved product/architecture question (production Rotate/Scale have it; Move does not), and it belongs to a decision, not a migration.

---

### Repository reality note

`git log -1` → `5701563 2026-09-17 Repo_Audit` (adds `docs/Repository_Wide Structural_Codebase_Health_Audit.md`). `git status --short` is empty. All test runs in this investigation used `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`; no files were created, modified, renamed or deleted.