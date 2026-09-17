I've completed the read-only audit. Below is the full report.

---

# Mirai-Bastel — Repository-Wide Structural / Codebase Health Audit

**Method note:** everything below is from reading files, `git` inspection and *read-only* test runs. Test runs used `PYTHONDONTWRITEBYTECODE=1` and `pytest -p no:cacheprovider` so no cache/bytecode files were written. `git status --short` is empty after the audit — **the repository is unmodified**.

**Evidence base:** `AGENTS.md`, `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md`, `CLAUDE.md`, root/`src`/`tests`/`experiments`/`playground` READMEs, `docs/architecture/*` (SOURCE_ARCHITECTURE, ROADMAP, INPUT_COMMAND_TOOL_CONTRACT, CORE_V1_FREEZE, ADR-001), `docs/design/artist_playground/*` (ARCHITECTURE_MAP, EXPERIMENT_HOST, DEV_HOST_AUDIT, ROADMAP, RESEARCH_MAP), `docs/research/viewport/production_camera_gl_convention.md`, Integration-Lab reconciliation audit, all of `src/`, the full Playground runtime, the experiment test/build scripts, `git log`, and live test runs.

**Repository scale:** 450 tracked files — `experiments/` 161, `docs/` 106, `playground/` 85, `src/` 41, `tests/` 40. 278 Python files. Production (`src/`) is ~2 800 LOC; the Playground is the largest single runtime (~4 000 LOC, incl. a 1 411-line `window.py` and a 1 363-line legacy copy).

**Verified test reality (today, local):**

| Command | Result |
|---|---|
| `pytest tests --ignore=tests/test_extrude_tool.py` | **398 passed** |
| `pytest playground/tests` | **233 passed** |
| bare `pytest` (repo root) | **46 collection errors, exit 1** |
| `python -m tests.run_core_suite` | documented path, separate runner |

---

# 1. Architecture Drift

### D1 — The top-level package name `viewport` exists twice, in Production and in an experiment, and the collision breaks repo-wide tooling

**Location:** `src/viewport/` vs `experiments/mirai_bastel_viewport_V1/viewport/`; triggered via `tests/_bootstrap.py` and the experiment's own `sys.path` bootstrap.

**Observation:** Running bare `pytest` from the repo root produces 46 collection errors in *both* directions:

```
experiments/.../tests/test_camera_picking.py: from viewport import vecmath as v
E   ImportError: cannot import name 'vecmath' from 'viewport' (C:\...\src\viewport\__init__.py)
tests/test_application.py: import tests._bootstrap
E   ModuleNotFoundError: No module named 'tests._bootstrap'
```

Two different meanings of `viewport` (Production render-data package, and the V1 experiment's window/tool package) are loaded through `sys.path` order rather than through distinct package names. `tests/_bootstrap.py` documents the ordering ("Füge src/ VOR dem Repo-Root ein") as load-bearing.

**Why it matters:** There is **no single command that verifies the whole repository green**. Any agent or CI step that runs plain `pytest` gets 46 errors that are *not* real code defects — an ideal trap for "let me fix the failing tests".

**Classification:** POSSIBLE ACCIDENTAL DUPLICATION (naming), TRANSITIONAL (V1 will presumably be retired or renamed).
**Confidence:** HIGH.

**Suggested next investigation:** Enumerate every top-level name that can be shadowed (`viewport`, `scene`, `adapters`, `_paths`, `deformation`, `articulation`, `demo_cylinder`) and decide which experiment must be renamed (e.g. `viewport_v1`) — but only after the V1 experiment's active status (see U1) is decided.

---

### D2 — Camera GL convention: Production was fixed, but the declared Single Source of Truth and both override subclasses still describe the broken state

**Location/evidence:**
- `src/mirai/viewport/camera.py:101-113` — `build_view_matrix()` **already** uses `-forward` in row 3 with `tz = +dot(eye, forward)`, and the comment at `:94-99` explicitly states the GL convention.
- Commit `bbeef97` (2026-09-12, *"docs/core(viewport): reconcile production architecture and camera convention"*) changed `src/mirai/viewport/camera.py` (±14 lines) and added the regression test `tests/test_camera_gate5_matrices.py::test_front_point_has_negative_view_z_and_positive_clip_w`.
- But `docs/research/viewport/production_camera_gl_convention.md` still says **`Status: INVESTIGATION — UNRESOLVED`**, documents Production as `row3 = +forward`, and states *"Keine Änderung an src/mirai/viewport/camera.py"*.
- `experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md §A.1` (dated 2026-09-08, head `9700c22`) — explicitly referenced as **the authoritative SSOT** by the research doc and by code — still says *"nur dokumentiert, NICHT behoben"*, describes the production matrix as clipping everything, and declares the Lab override **"load-bearing"**.
- `experiments/mirai_bastel_integration_lab/lab_camera.py:41-60` and `playground/camera.py:55-74` both override `build_view_matrix()` — byte-for-byte the same formula now in Production.

**Observation:** The override is now redundant relative to `OrbitCamera.build_view_matrix()`. It is harmless at runtime, but three code docstrings plus two documents assert a false premise and rate the override as essential.

**Why it matters:** This is the classic precondition for a *regression by documentation*: an agent reading the SSOT will "re-fix" a fixed camera, or will "clean up" the redundant override and then be told by the audit that the override was load-bearing. It is also an active maintenance cost in two experiments for a problem that no longer exists.

**Classification:** POSSIBLE ACCIDENTAL DUPLICATION (three implementations of one matrix) + stale documentation. The override itself was originally an intentional transitional adapter.
**Confidence:** HIGH.

**Suggested next investigation:** Confirm with the project owner whether the Playground/Lab overrides may be deleted, then reconcile the research doc and the audit §A.1 in one documented change (M1: also record *"X wird nicht verwendet, weil Y"*).

---

### D3 — The Playground has a hard, import-level dependency on two *experiment* directories, including its scene-asset path

**Location:** `playground/_paths.py:25-45` (puts `experiments/mirai_bastel_integration_lab` and `experiments/rigging-skinning-morphing` on `sys.path`), consumed by `playground/app.py:27-30` (`adapters.obj_to_core.build_core_scene_from_obj`, `frame_camera_on_bounds`), `playground/experiments/articulation/articulation.py` (`from deformation import Transform`), `demo_cylinder.py`, and `DEFAULT_HEAD_ASSET` → `experiments/rigging-skinning-morphing/meshes/head_basemesh.obj`.

**Observation:** The dependency direction research→experiment is legitimate. What matters is *what* became load-bearing: the camera framing helper, the OBJ→Scene adapter, the head asset and a deformation primitive now live in experiment dirs that the Architecture Map classifies as `⚫ OUT` (Lab), `🟡 ADAPT`, or a *"separate technical research track"* (rigging).

**Why it matters:** A future cleanup of the Integration Lab or the rigging experiment — both explicitly "disposable" by policy — silently breaks the *only runnable application in the repository*. The Architecture Map already lists the Lab as `🟡 ADAPT "too specific for its current purpose … the Lab stays as a reference implementation"`, which no longer matches reality: it is now a shared helper library.

**Classification:** INTENTIONAL RESEARCH DUPLICATION (originally "Wiederverwendung statt Duplikat"), but the resulting coupling is now **TRANSITIONAL and undocumented as such**.
**Confidence:** HIGH.

**Suggested next investigation:** Decide whether `adapters.obj_to_core` + the head asset should have a small production home (or a Playground-local copy) *before* any Lab/rigging cleanup is scheduled.

---

### D4 — The accepted Input→Command→Tool contract is declared and tested but not implemented by any running application

**Location:** `src/mirai/interaction/commands.py` (defines `SELECT`, `ORBIT`, `PAN`, `ZOOM`, `CYCLE_DISPLAY_MODE`, `SET_VERTEX/EDGE/FACE_MODE`, `TOGGLE_WIREFRAME_OVERLAY`, …), `src/mirai/interaction/bindings.py:50-98`, `src/mirai/application.py:103-125`, `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md`.

**Observation:** `Application.dispatch_command()` handles only tool commands (Move/Rotate/Scale) and UNDO/REDO; every selection/navigation/display command falls through to `return False`. The contract document is marked *"implementiert und praktisch validiert im Viewport-V1-Experiment"* — i.e. validated in an experiment, not in Production. The only runtime window (`playground/window.py`) uses none of it.

**Why it matters:** The production command set is effectively an interface *sketch*: it can be read as though these actions exist. The Input/Command layer is exercised only by `tests/` and by `PlaygroundApp.undo()/redo()` (two calls, `playground/app.py:202/205`).

**Classification:** TRANSITIONAL (documented as intentionally open in `SOURCE_ARCHITECTURE.md §5`), but the *docs* describe it in the present tense.
**Confidence:** HIGH.

**Suggested next investigation:** Add an explicit "declared but unhandled commands" note to `INPUT_COMMAND_TOOL_CONTRACT.md` (or mark them planned) so the contract matches runtime behaviour.

---

### D5 — "Rendering" ownership does not match the documentation

**Location:** `src/viewport/viewport.py:79-87` (`render()` is a documented no-op), `src/viewport/resource_store.py:136` (`PygletStore` — real GL backend), `playground/window.py:117-190` (own Phong + overlay shaders), `:347-473` (own VBO builders), `playground/vbo_builder.py`, `docs/design/artist_playground/ARCHITECTURE_MAP.md` (*"The only complete renderer in the repository"*).

**Observation:** Grep for `PygletStore` outside `src/viewport` returns only docstring mentions — no runtime consumer exists. The drawn pixels in the only live application come from `PlaygroundWindow`'s own shaders and VertexLists built by `playground/vbo_builder.py` from `viewport.render_mesh.derived`. `PlaygroundRenderer.render()` calls the production no-op and then the window draws from its own VBOs.

**Why it matters:** `src/viewport` is a *render-data + dirty-state + resource* engine, not a renderer, despite how the Architecture Map and `src/viewport/__init__.py` describe it. "Where is the renderer?" is answered "Playground" at runtime and "src/viewport" in documentation. A future production entry point will have to write the draw call anyway, and there is little evidence yet about how much of the window's shader/VBO code is reusable (it is considerably simpler than the scoped/dirty-state V0.2 design).

**Classification:** UNCLEAR (documented split in `PlaygroundRenderer`'s docstring, contradicting the Architecture Map) — a partial accidental duplication of render-data construction.
**Confidence:** HIGH for the facts, MEDIUM for the impact judgment.

---

### D6 — The Core freeze record no longer lists all Core extensions

**Location:** `docs/architecture/CORE_V1_FREEZE.md §7.1` (only the ADR-001 Transform promotion), `src/core/mesh.py:197` (`add_edge`), commit `50fbee8`, tests `tests/test_core.py:128-165`.

**Observation:** `Mesh.add_edge()` was added to frozen `src/core` during AP-05 and is covered by an architecture-contract test (including error cases and invariants), and it is documented in `docs/architecture/ROADMAP.md §13` and the AP-05 roadmap. But the freeze document — the document that defines *which* exceptions are authorized — does not mention it.

**Why it matters:** The freeze/exception procedure is the project's main protection against silent architectural change. If the record of authorized exceptions is incomplete, the procedure looks weaker than it is, and the next agent has no precedent to cite.

**Classification:** Documentation drift (implementation is correct and test-backed; the record lags).
**Confidence:** HIGH.

---

# 2. Responsibility / Ownership

### O1 — `playground/window.py` is a single 1 411-line object owning at least nine distinct responsibilities

**Location:** `playground/window.py`

**Observation (concrete inventory, not "it's big"):**
- pyglet window + event dispatch: `on_mouse_press/drag/motion`, `on_key_press/release` → `:642-1388`
- GL shader sources and programs: `:117-179`, `:273-280`
- VBO construction for faces/edges/vertices/selection/hover: `:347-473` (+ `playground/vbo_builder.py`)
- the actual draw pass and display-mode interpretation: `:1392-1411+`
- per-family semantics: selection dispatch, presentation slot cycling, transform activation models, four Tweak variants, extrude/loop-insert/loop-slide/connect tool ownership, articulation gesture start/axis derivation
- articulation math owned by the window: `_mesh_bounding_radius()` at `:196-213` and the axis derivation comment at `:707-729` (`axis = normalize(-dx·forward + dy·right)`)
- ESC precedence chain over six competing interaction states: `:1280-1320`
- HUD wiring: `_update_hud()` at `:477-508`

**Why it matters:** The docs assign interaction semantics to the Experiment Host/variants and rendering to the Viewport. In practice the *window* is the arbiter of both, and every new interaction feature grows this one file. Its state machine is implicit (eleven `_tweak_*` flags, articulation flags, transform flags) and is not directly unit-testable except through headless mirrors.

**Classification:** ACTIVE. Structural concentration, not accidental duplication — but it is the highest-risk single node in the repository.
**Confidence:** HIGH.

**Suggested next investigation:** Before the next interaction family is added, decide whether the per-family interpreters should be extracted into the Experiment Host (e.g. an `Experiment.handle_key/handle_drag` contract) — the Host audit already notes *"the current implementation should still be treated as an experiment host rather than as a finished production tool system"*.

---

### O2 — Two competing "active tool" authorities

**Location:** `src/mirai/interaction/tool_manager.py:44-46` (`ToolManager.active_tool`), `src/mirai/application.py:66-67`, `playground/app.py:71` (`self.active_tool = None`), `playground/window.py:1257/1269` (`self.app.active_tool = create_tool_for_type(...)`), `playground/transformer.py:26-34`.

**Observation:** The Playground creates tools directly with `create_tool_for_type()` and stores them in `PlaygroundApp.active_tool`, plus separate ad-hoc fields `_tweak_tool`, `_extrude_tool`, `_loop_slide_tool`. `Application.tool_manager` (which enforces the documented one-active-tool lifecycle contract from `tool.py`) is still constructed (`application.py:66`) but its `active_tool` remains `None` throughout a Playground session.

**Why it matters:** The production Tool lifecycle contract (cancel-before-switch, `INTERACTING` guards) is bypassed by the live application. A reader asking "where is the active tool?" finds two answers with different invariants.

**Classification:** TRANSITIONAL (documented in the Architecture Map as `🔵 WRAP Tool System — Playground router needed`).
**Confidence:** HIGH.

---

### O3 — Selection behaviour has no production owner

**Location:** `src/core/selection.py` (state: `Selection`, `SelectionMode`, `hovered`), `playground/selector.py` (behaviour: `SelectMode` REPLACE/MODIFIER/TOGGLE, `SelectMethod` PICK/BOX/LASSO/PAINT, `dispatch_click`), `playground/app.py:69-70` (`select_mode`, `select_method`), `playground/window.py` (mode/component keys).

**Observation:** Core owns selection *state* and a `mode` enum; all selection *behaviour* (what a click does, box select, modifiers, component-mode dispatch) lives in the Playground. `SelectMethod.LASSO/PAINT` are declared stubs returning `False` (`selector.py:266-267`).

**Why it matters:** "Where does selection live?" has a clean answer for state and no answer for behaviour. This is exactly the area the project has flagged as its most important research question, so the ambiguity will be resolved by promotion — but until then `Selection.mode` is written from several layers (core, selector, window, topology tools).

**Classification:** UNCLEAR (behaviour intentionally un-promoted).
**Confidence:** HIGH.

---

### O4 — HUD / presentation ownership is split between two implementations

**Location:** `playground/hud.py` (`PlaygroundHUD`), `experiments/mirai_bastel_integration_lab/integration/lab_viewport.py` + `tests/test_hud.py`.

**Observation:** The Architecture Map prescribed `🟡 ADAPT "HUD ← extract to PlaygroundHUD"`; that extraction happened. The Lab's own HUD remains in its window. Low risk, expected for an experiment.

**Classification:** ISOLATED PROTOTYPE (healthy).
**Confidence:** HIGH.

---

# 3. Duplicate and Parallel Implementations

| Concept | Locations | Classification | Confidence |
|---|---|---|---|
| Topology primitives | `playground/topology_tools/{connect_edges,loop_insert,loop_ring,loop_slide,extrude}.py` vs `experiments/mirai_bastel_viewport_V1/viewport/{topology_tools,loop_ring,extrude_tool}.py` | **INTENTIONAL RESEARCH DUPLICATION** — declared 1:1 logic ports against `src/core` (not the V1 core fork), with the deliberate deviation noted (`_SnapshotCommand` → `MeshStateCommand`) | HIGH |
| Camera view matrix | `src/mirai/viewport/camera.py`, `experiments/.../lab_camera.py`, `playground/camera.py` | **POSSIBLE ACCIDENTAL DUPLICATION** (all three now identical; see D2) | HIGH |
| Core | `src/core/*` vs `experiments/mirai_bastel_core_V1/mirai_bastel_core/*` | **INTENTIONAL** archive/reference copy (project memory; M1). Note the extra `mirai_bastel_core/move.py` beside `operations/move.py` | HIGH |
| Viewport v0.2 | `src/viewport/*` vs `experiments/mirai_bastel_viewport_V02/*` (same module names: `camera`, `render_mesh`, `derived`, `category`, `selection`, `material`) | **TRANSITIONAL** — declared `⚫ OUT`, purpose fulfilled; still a name-shadowing hazard (D1) | HIGH |
| Render data | `src/viewport/{derived,overlay,render_mesh}` vs `playground/vbo_builder.py` + window shaders | **POSSIBLE ACCIDENTAL DUPLICATION** at the draw-data level (window reuses `render_mesh.derived` for normals but rebuilds all VBOs itself) | MEDIUM |
| Interaction input | `src/mirai/interaction/{input,bindings,commands,routing}` vs `playground/input_map.py` + hardcoded keys in `window.py` vs `experiments/.../viewport/{input_binding,default_bindings,commands}.py` | **TRANSITIONAL / UNCLEAR** — three input maps; see AI-H2 | HIGH |
| Tools | `src/mirai/interaction/tools/*` vs `playground/topology_tools/*` vs V1 `move_tool/transform_tool/extrude_tool.py` | **INTENTIONAL** (Playground Topology tools are new research; Move/Rotate/Scale are reused from Production) | HIGH |
| Windows | `playground/window.py` vs `playground/experiments/articulation/_old_/window.py` (1 363 lines) | **LEGACY/DUPLICATE** — committed deliberately as `"articulation old files"` (`f9b3ead`), imported by nothing | HIGH |
| Core module copies in tests | `tests/mesh.py`, `tests/history.py`, `tests/operations_init.py` | **POSSIBLY DEAD / DUPLICATE** — `tests/mesh.py:34` imports `from .ids import …` but `tests/ids.py` does not exist, so the file cannot even be imported | HIGH |
| Same document twice | `docs/CORE_ARCHITECTURE_REASSESSMENT.md` and `docs/Mirai-Bastel — Core Architecture Reassessment.md` | **POSSIBLE ACCIDENTAL DUPLICATION** — byte-identical (hash `9259B77D…`) | HIGH |
| Same document, two revisions | `docs/Cline - Work Package WP-01A.md` (10 572 B) vs `docs/Mirai-Bastel — Work Package WP-01A.md` (11 556 B); same for WP-02 (6 352 B vs 12 816 B) | **UNCLEAR** which revision is authoritative — not identical, no linking between them | MEDIUM |
| Verdict/decision records | `playground/experiments/selection/decision.md`, `playground/experiments/tweak/tweak_decision.md` | INTENTIONAL, both explicitly `Status: OFFEN — noch nicht gespielt` | HIGH |
| Legacy smoke/diag scripts | `experiments/mirai_bastel_viewport_V1/_smoke_*.py`, `playground/_diag_screenshot.py`, `playground/_diag_head_view.png` | ISOLATED/LEGACY tooling kept as evidence | MEDIUM |

**Explicit non-recommendation:** the Playground↔V1↔V02 topology/rendering overlaps should **not** be merged merely because they look similar. They encode the project's stated method (prototype → port against production → decide). The camera duplication (D2) is the one case where the duplication is *already obsolete* rather than exploratory.

---

# 4. Legacy / Dead / Transitional Inventory

**ACTIVE**
- `src/core/*` (extendable per ADR-001; frozen-by-default per `CORE_V1_FREEZE.md`), `src/mirai/*` (fully test-covered), `src/viewport/*` (Gate 5/7 verified).
- `playground/*` — the only runnable application; its variant families are live research assets per `DEV_HOST_AUDIT.md`.
- `experiments/mirai_bastel_integration_lab/*` (Production-based since WP-IL-01; now also a shared helper source), `experiments/rigging-skinning-morphing/*` (separate research track; supplies the Playground's head asset and `deformation.Transform`), `experiments/topology/` (documentation-only SSOT).

**EXPERIMENTAL**
- `playground/experiments/*` (six families), all `playground/topology_tools/*`.

**TRANSITIONAL**
- `experiments/mirai_bastel_viewport_V02/*` (declared `⚫ OUT`), `experiments/mirai_bastel_viewport_V1/*` (see U1), `lab_camera.py` / `PlaygroundCamera` overrides (D2).

**LEGACY**
- `playground/experiments/articulation/_old_/` (articulation.py, test_articulation.py, window.py — 1 881 lines added in one commit explicitly labelled *old files*).
- `experiments/mirai_bastel_core_V1/` — intentionally preserved archive.

**POSSIBLY DEAD** (documented cleanup candidates that were *recommended in `docs/WP-04_AGENT_VERIFICATION_REPORT.md` (2026-09-01), explicitly delegated to "Manuel entscheidet", and never executed)
- `tests/mesh.py`, `tests/history.py`, `tests/operations_init.py` — *"nirgends importiert"* (verified: nothing imports them).
- `tests/mnt/user-data/outputs/phase_e/` — sandbox artifact tree with a copied runner.
- `tests/phase_d.patch` (14 606 B), `tests/full_hardening_d_e.patch` (17 862 B) — patch files sitting in the test directory.
- `tests/test_extrude_tool.py` — imports `mirai_bastel_core` and `viewport.extrude_tool`, neither reachable by its own (wrong) `sys.path` manipulation; documented as excluded in `tests/README.md`.
- `_measure_coverage.py` (root) — self-described *"Temporary Gate-3 coverage measurement"*; **still referenced by `CLAUDE.md` as a project tool**.
- `src/viewport/resource_store.py::PygletStore` — no runtime consumer found (see D5).
- `run_output.log` (0 bytes, gitignored).

**UNCLEAR**
- `experiments/mirai_bastel_core_V1/mirai_bastel_core/move.py` (alongside `operations/move.py`).
- The WP-01A/WP-02 filename pairs (two revisions, no cross-reference).
- Whether `docs/WP-01-BUGS_AND_TODOS.md` (93 bytes: two lines about camera/lighting in the Playground) is still a live tracking document or a note-to-self.

> Per the audit brief I did **not** treat absence of imports as proof of death; in each "POSSIBLY DEAD" case there is a second signal (explicit doc statement, broken import, or 0-byte/no-consumer).

---

# 5. AI-Hostile Ambiguity

**AI-H1 — Two `window.py` implementations for the same Playground.** `playground/window.py` (1 411 lines, active) and `playground/experiments/articulation/_old_/window.py` (1 363 lines, legacy, near-identical imports). Both define `PlaygroundWindow`. Nothing imports the old one, but nothing in the code marks it as dead either — only the commit message does. *An agent searching for "PlaygroundWindow" or "where is key G handled?" gets two plausible hits.*

**AI-H2 — Three input authorities with conflicting key semantics.**
- Production (`src/mirai/interaction/bindings.py`): `o` = cycle display, `w` = wireframe overlay, `m` = Move, `v/1` = vertex mode, `ctrl+z/y` = undo/redo, `esc` = cancel.
- Playground `input_map.py`: `d` = display cycle, `z` = wireframe overlay, `v` = show vertices.
- Playground `window.py` (hardcoded): `m` = cycle SelectMode, `q` = cycle SelectMethod, `1/2/3` = component mode, `x/r/s` **held** = transform, `e/i/j/k/g` = topology tools, `tab` = cycle focused family.

Five of these letters (`m`, `v`, `z`, `1`, `r/s`) mean *different things* in the two systems, and the Playground manual documents only the Playground meaning. *An agent "aligning the Playground with the production bindings" would silently break the artist's muscle memory — the very thing the Playground exists to research.*

**AI-H3 — `tests/mesh.py` / `tests/history.py` look like Core.** Their module docstrings are the Core docstrings verbatim ("Mesh: Topologie-Domain-Modell … Architekturvertrag: …"). A grep for `def split_edge` or `class HistoryStack` returns two implementations, one of which cannot be imported.

**AI-H4 — Three "OrbitCamera" classes with two documented, mutually contradictory matrix conventions** (D2). Choosing "the right camera" requires reading an SSOT that is factually outdated.

**AI-H5 — `viewport` and `_paths` as top-level names in multiple places** (`src/viewport`, `experiments/.../viewport_V1/viewport`, `experiments/.../viewport_V02/`; `playground/_paths.py` vs `experiments/mirai_bastel_integration_lab/_paths.py`). `import viewport` and `import _paths` are order-dependent, not identity-dependent. `sys.path` insertion order inside `_paths.py` is load-bearing and invisible at call sites.

**AI-H6 — "experiments" means two different things.** `experiments/` (repository-level research areas, disposable by policy) and `playground/experiments/` (variant families inside the research host, also disposable but *promotable*). An agent following `AGENTS.md §7 ("experiments/ is the research and prototype area … may be disposable")` could reasonably conclude that Topology tools should not be relied upon, while `DEV_HOST_AUDIT.md` says they are real, current capability.

**AI-H7 — Doc-string promises that exceed reality.** `src/viewport/viewport.py`/ARCHITECTURE_MAP describe a "complete renderer"; `render()` is a no-op and `PygletStore` has no consumer. `commands.py` declares commands that `dispatch_command` never handles.

---

# 6. Tests and Verification

### T1 — There is no single trustworthy green command, and the naive one fails loudly

**Location:** repo root (no `pytest.ini`, no `pyproject.toml`, no `setup.cfg`, no `conftest.py`, no `tests/__init__.py`); `tests/_bootstrap.py`; experiment-local bootstraps.
**Observation:** `pytest tests --ignore=tests/test_extrude_tool.py` → 398 passed; `pytest playground/tests` → 233 passed; bare `pytest` → 46 collection errors.
**Why it matters:** A machine-checkable "is the repo healthy?" signal does not exist. The error text (`ModuleNotFoundError: No module named 'tests._bootstrap'`) actively suggests a wrong fix.
**Classification:** Verification-structure gap (not a code defect).
**Confidence:** HIGH.

### T2 — `tests/README.md` describes a suite that no longer matches the code

**Observation:** It documents the baseline as *"29/29 unittest-Tests"* plus a separate `python -m unittest …` set, and as its most complete command `pytest tests --ignore=tests/test_extrude_tool.py` — which today collects **398** tests. It does not mention `playground/tests` (233 tests) at all, nor that bare `pytest` is broken, nor the 25 WP-04 tests as part of a green set.
**Why it matters:** The document that defines "what is trusted" understates the trusted set by an order of magnitude and omits an entire green test area.
**Confidence:** HIGH.

### T3 — A production test area contains a Playground test

**Location:** `tests/test_playground_transformer.py` (`from playground._paths import ensure_paths`, `from playground.transformer import …`).
**Observation:** The only tests of `playground/transformer.py` live in `tests/`, which `tests/README.md` defines as "Tests für Production-Core, Application/Interaction und Viewport". `playground/tests/` exists but has no transformer test.
**Why it matters:** Blurs the promotion boundary in the verification layer: a green production suite implies coverage of an experimental adapter.
**Confidence:** HIGH.

### T4 — `tests/test_extrude_tool.py` names a capability that does not exist in Production

**Observation:** The file is excluded from the documented run, imports `mirai_bastel_core` and `viewport.extrude_tool` (neither resolvable), and duplicates V1's `tests/test_extrude_tool.py` (373 lines) against the *experiment's* modules.
**Why it matters:** Reading the file list suggests extrude is covered in Production. It also forces every documented command to carry `--ignore=`.
**Confidence:** HIGH.

### T5 — Whole runtime paths are only ever verified headlessly

**Observation:** The production viewport, camera, picking, display and the entire Input/Binding/ToolManager layer are covered by fast headless tests, and the Integration Lab contributes real-GL probe tests, but the production draw path (`Viewport.render()`) does not exist and `PygletStore` has no runtime consumer. The only continuous live GL verification is *manual, by the artist, through Playground/V1/Lab windows*.
**Why it matters:** "Tests are green" therefore says nothing about the one integration (mesh → GPU pixels) that has historically produced the project's worst surprises (the clipping bug). The camera convention now at least has a headless regression test (`test_camera_gate5_matrices.py`) — good — but nothing pins the draw path.
**Confidence:** HIGH for the facts; MEDIUM that a fix is warranted now (a production entry point is deliberately out of scope).

### T6 — Three test trees with colliding module basenames

`tests/`, `playground/tests/`, `experiments/*/tests/` share names (`test_camera_picking.py`, `test_tool_lifecycle.py`, `test_extrude_tool.py`, `test_tool_integration.py`, `test_input_binding.py`, …). Only `tests/` and `playground/tests/` are demonstrably green; the experiments' tests are individually runnable only with their own bootstrapping and currently collide with `src/viewport` (D1). `tests/README.md` does not state which trees are expected to be green.
**Confidence:** HIGH.

**Positive finding worth keeping:** `tests/mesh_invariants.py` is a genuinely good cross-cutting invariant harness, reused by five test modules, and it checks only the public query API (so it survives internal restructuring). The Core suite's error-decision rule (`tests/README.md`) is explicit and correct.

---

# 7. Documentation ↔ Implementation Drift

| # | Document | Drift | Type |
|---|---|---|---|
| 1 | `docs/research/viewport/production_camera_gl_convention.md` (`Status: UNRESOLVED`) | Production camera was fixed in `bbeef97`; doc still describes row 3 = `+forward` and "no change to `src/mirai/viewport/camera.py`" | **Stale documentation** |
| 2 | `experiments/.../ARCHITECTURE_RECONCILIATION_AUDIT.md §A.1` (declared SSOT) | Same, plus *"das Lab importiert kein einziges Symbol aus src.mirai/src.viewport"* — superseded by the WP-IL-01 rebase the same document recommends; also records `383 passed` (today 398) | **Stale documentation** (audit is historical-by-date but referenced as current SSOT) |
| 3 | `docs/design/artist_playground/ARCHITECTURE_MAP.md` | *"The only complete renderer in the repository"* for `src/viewport` (no draw call exists); Lab classified `🟡 ADAPT`, reality = shared helper library used by the Playground | **Implementation drift** |
| 4 | `docs/design/README.md`, `docs/README.md`, `docs/architecture/README.md` | Do not index `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` (the *binding spec* referenced by 14 files in `src/viewport/`), `docs/ADR-001-…`, `docs/design/artist_playground/{EXPERIMENT_HOST,RESEARCH_MAP,DEV_HOST_AUDIT,UX_RESEARCH,AP-03_PLAN}.md`, or `docs/project planning/…`. The viewport spec is reachable only via `ROADMAP.md:427` and a WP-04 audit row | **Navigation drift** |
| 5 | `CLAUDE.md` | Instructs agents to use `_measure_coverage.py` ("Temporary Gate-3 coverage measurement") and `pytest tests/ -v` (fails without `--ignore`) | **Stale agent guidance** |
| 6 | `tests/README.md` | "29/29" baseline vs 398 collected; `tests/playground_transformer.py` boundary; bare-`pytest` breakage undocumented | **Numeric + structural drift** |
| 7 | `experiments/README.md` | Describes `mirai_bastel_viewport_V1/` as the *active* interactive research field for selection/topology; in practice the Playground is that field and V1's topology code has been ported out | **Unclear status** |
| 8 | `docs/architecture/CORE_V1_FREEZE.md §7.1` | Does not record the `add_edge()` Core extension (D6) | **Incomplete record** |
| 9 | `docs/CORE_ARCHITECTURE_REASSESSMENT.md` == `docs/Mirai-Bastel — Core Architecture Reassessment.md` | byte-identical; two homes for one canonical text | **Accidental duplication** |
| 10 | `docs/WP-01A` / `WP-02` filename pairs | Different revisions (10 572 vs 11 556 B; 6 352 vs 12 816 B), neither referencing the other | **Unclear authority** |
| 11 | `docs/design/artist_playground/ROADMAP.md` | **Not drift** — explicitly self-correcting ("must not describe planned work as missing when it already exists"), dated 2026-09-15, matches the code. This document worked. | Healthy |

Also worth recording as *intentional experimental divergence* (not drift): the Playground's Y default camera angle, its GL shaders, its key map and its ad-hoc tool ownership all deliberately differ from Production while the production surfaces are frozen — this is stated in `PlaygroundCamera`'s docstring and `playground/README.md`.

---

# 8. Local Repository Hygiene

- Working tree is **clean**; 35 ignored entries are `__pycache__/`, `.pytest_cache/` and `run_output.log` (0 bytes) — all correctly gitignored. `.idea/` present locally, ignored. No stale local-only work appears to be at risk.
- **Tracked, but local-tooling in nature:** `.claude/settings.local.json` — contains absolute local paths (`C:\Users\Manuel\…`) and broad allow rules (`Bash(python *)`, `Bash(git *)`). Harmless, but it is a per-machine config living in version control.
- **Tracked diagnostic artifacts:** `playground/_diag_head_view.png` (~5.9 KB) and `playground/_diag_screenshot.py` (54 lines, writes PNGs next to itself), both from the Integration-Lab bug hunt. They are evidence, but they are also the only ignored-looking files inside a production-adjacent directory.
- **Tracked AI/sandbox artifacts:** `tests/mnt/user-data/outputs/phase_e/**`, `tests/phase_d.patch`, `tests/full_hardening_d_e.patch`, `docs/WP-04_DELIVERABLE_MAP.txt` (a delivery inventory referencing `/mnt/user-data/outputs/`).
- `docs/` contains **35 `WP-04_*` gate documents** plus three WP-01/WP-02 documents in two naming families and two byte-identical copies. The docs tree is ~106 tracked files, i.e. more documentation files than production Python files (`src/` = 38). This matches the project's own honest note in `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md §9`: *"Mirai-Bastel hat viel Dokumentation relativ zu ausgelieferten Features."* — worth naming as an observation, not a recommendation to delete (archive policy is intentional).
- No generated/build output is committed. No virtualenv. Python 3.14.2 in use while `CLAUDE.md` states "Python 3.9+"; `README`/docs don't pin a version.

---

# AI-Hostile Ambiguity (consolidated)

1. **AI-H1** Two `PlaygroundWindow` implementations (active + `_old_`), both plausible edit targets.
2. **AI-H2** Three input maps; five reused letters with different meanings; production bindings unused by the running app.
3. **AI-H3** `tests/mesh.py` / `tests/history.py` mirror Core class/module names *and* docstrings.
4. **AI-H4** Three `OrbitCamera` classes; the authoritative discussion document is factually outdated and marked "UNRESOLVED".
5. **AI-H5** Duplicate top-level package/module names resolved by `sys.path` order (`viewport`, `_paths`).
6. **AI-H6** "experiments" means two different things at two different levels.
7. **AI-H7** Present-tense claims in docs/code comments that exceed the implementation (renderer, commands).
8. **AI-H8** Two byte-identical canonical-document copies and two divergent WP-01A/WP-02 revision pairs with no authority marker.

---

# Healthy / Intentional Complexity (do not mistake for problems)

- **`src/core`** — 420-line `mesh.py` with a documented query-only API, invariant harness, and a real regression suite. Dependency-clean (no UI/GL/input imports anywhere in `src/core`). The freeze + ADR-001 extension path is a working mechanism, not bureaucracy (it produced a test-backed `add_edge()` rather than an ad-hoc mutation).
- **`src/viewport` dependency direction** — verified: it imports only `core` and duck-types the camera; `src/mirai` imports it at the Application boundary. The documented "Core knows nothing about Viewport" rule holds.
- **Experiment preservation** — V1, V02, Core V1 and the rigging track are kept as evidence, exactly as `AGENTS.md`/`MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` (M1) prescribe. Their apparent duplication is the project's memory.
- **Playground research model** — one variant per research question, `ExperimentSlot` as a container (not a framework), no combination matrix (`RESEARCH_MAP.md` explicitly forbids status columns/coverage metrics), decision templates with a *deliberately empty* "Production Migration Notes — bewusst leer bis ein Verdict vorliegt". The written research questions in `tweak_decision.md` (2×2 activation axis, controlled variables, pre-registered observations) are unusually disciplined.
- **The empty verdicts are honest, not a defect** — both `decision.md` files say `OFFEN — noch nicht gespielt`. The loop's *decision* half simply hasn't run yet; that is a state, not a bug.
- **Playground test coverage of experimental logic** — 233 headless tests over selector/transformer/topology tools/slot/presentation/camera mean the variants are cheap to keep changing. That is exactly the right kind of verification for research code.
- **`phases/`-style experiment pragmatism** — `lab_viewport.py` monolith, V1 `test_all_tools.py` monolith etc. are within the "experiments may be pragmatic and disposable" rule.

---

# Unclear Ownership

| Concept | Where it lives | The open question |
|---|---|---|
| Rendering (draw) | `src/viewport` (no draw call) / `playground/window.py` (draws) | Which is the future production renderer's home, and how much of the window's shader/VBO code survives? |
| Interaction semantics of variants | `playground/window.py` (imperative) vs `Experiment` variants (`playground/experiments/*`) | The Host defines a `draw/update/activate` contract but the window implements the *semantics* of every family. Which layer owns a family's behaviour? |
| Selection behaviour | `playground/selector.py` + `app.select_mode` + `window` keys | No production counterpart; promotion target undecided. |
| Active tool | `Application.tool_manager` (unused) vs `PlaygroundApp.active_tool` + window fields | Which lifecycle contract governs future production tools? |
| OBJ loader / framing / head asset | `experiments/rigging-skinning-morphing`, `experiments/mirai_bastel_integration_lab` | Load-bearing for the only running app while classified as `⚫ OUT`. |
| V1 viewport experiment status | `experiments/mirai_bastel_viewport_V1/` | Docs call it active; the Playground has taken over its role and its topology code was ported. |
| `docs/WP-01A` / `WP-02` revision pairs | two files each | Which revision is current? |

---

# Areas That Should NOT Be Touched

1. **`src/core/`** — extend only with a documented decision + tests (ADR-001 / `CORE_V1_FREEZE.md §7` procedure). The mechanism is proven; do not "modernize".
2. **`src/viewport/` + its Gate 5/7 tests** (`test_render_mesh`, `test_dirty_state`, `test_resource_store`, `test_derived_geometry`, `test_overlay`, `test_viewport_facade`, `test_benchmark_scenarios`, camera matrix/Gate 7 tests) — verified green and the only expression of the incremental-update architecture.
3. **`src/mirai/interaction/*` lifecycle contracts** (`tool.py`, `tool_manager.py`) and their tests (`test_tool_lifecycle`, `test_tool_manager`, `test_routing`, `test_input_binding`) — a validated, configurable binding design. Do not "unify" it with the Playground's ad-hoc routing before a promotion decision.
4. **Playground variant families and their decision documents** (`playground/experiments/*`, `decision.md`, `tweak_decision.md`) — variants must survive until verdicts exist. "Cleanup" here destroys the experiment.
5. **`tests/mesh_invariants.py` and the Phase A–E hardening tests** — the Core's regression safety net.
6. **`experiments/mirai_bastel_core_V1/`, `…viewport_V1/`, `…viewport_V02/` as *content*** — M1/project memory. (Their *naming* may need attention for D1, but not their evidence.)
7. **`experiments/topology/`** — declared active SSOT for topology research direction; link, don't duplicate.
8. **`docs/design/artist_playground/{ROADMAP,RESEARCH_MAP,EXPERIMENT_HOST,DEV_HOST_AUDIT}.md`** — recent, reality-checked, and explicitly self-correcting. Update only with new evidence; do not restructure the process (the development system forbids new mechanisms without an observed failure).

---

# Executive Summary

**Overall structural health: good, with two localized problem clusters and one systemic verification gap.**

The foundation is genuinely healthy. `src/core` is small, dependency-clean, frozen-by-default with a working exception procedure, and backed by a real invariant/regression suite. `src/viewport` respects the documented dependency direction and survived a Proof-of-Architecture review. The experiment/production separation is not just documented, it is *practised*: topology primitives were re-ported against production core rather than copied; the Core was extended only after a demonstrated need; variants are containers, not code forks. Documentation-to-code drift exists but is mostly *lag*, not contradiction — and the Playground's own roadmap explicitly instructs readers to check the code before declaring a capability missing.

Three things do deserve attention.

First, **the repository has no single command that verifies it, and the naive command fails with 46 errors** caused by real architecture (two packages named `viewport`, three test trees with colliding module names, `sys.path` ordering as an invisible contract). This is the most consequential finding because it is the one that will mislead every future agent — including one asked to "fix the failing tests".

Second, **the camera-convention cluster**: the production bug was fixed, but the declared SSOT, a research document, and three code docstrings still describe it as an unresolved production defect and rate two now-redundant overrides as load-bearing. This is the sharpest example of the repository's broader risk: *authoritative-looking, dated documents inside experiment directories* that were correct when written and are now wrong, while code carries workarounds whose comments assert the outdated premise.

Third, **responsibility concentration in `playground/window.py`** (1 411 lines, nine responsibilities, an eleven-flag implicit state machine) combined with the fact that the Playground — classified as research and allowed to be disposable — now *loads* two experiments (`adapters.obj_to_core`, `deformation.Transform`, the head asset) and bypasses the production Input/Command/Tool layer entirely. The Playground has become the real application while retaining a research classification, and nothing in the repository states that transition explicitly.

None of this looks like accidental complexity in the classic sense. There is almost no speculative abstraction, no premature framework, no dead architecture that was never used. The complexity is *accumulated evidence*: multiple experiments, multiple dated audits, multiple attempts at the same interaction question — exactly what the project's method asks for. The cost is findability and authority (which document/code path is current), not design.

The `_old_` window duplicate, the shadow Core copies in `tests/`, the sandbox artifact tree, the two byte-identical copies of one document, and the "29/29 vs 398" test-count drift are all small, cheap, and — importantly — most of them were *already identified* in `docs/WP-04_AGENT_VERIFICATION_REPORT.md` and deliberately left for the project owner. That is the single most encouraging signal in this audit: the repository's own record-keeping is honest, and it knows what its own debris is.

**Nothing in this audit indicates that refactoring is required now.** The recommendation is to close the authority gaps (D1, D2, D6, doc indexes, test documentation) and to decide the *status questions* (V1 experiment, Playground-as-application, load-bearing experiment helpers) before touching any code.

---

# Follow-up Investigation (before any refactoring decision)

1. **Camera cluster (D2):** Confirm that `OrbitCamera.build_view_matrix()` is now authoritative for GL. If yes, may `LabOrbitCamera.build_view_matrix` and `PlaygroundCamera.build_view_matrix` be deleted, and which document becomes the new SSOT for the (now historical) finding?
2. **`viewport` naming (D1):** Is `experiments/mirai_bastel_viewport_V1/` still an active research field, or is it archive-able/rename-able (e.g. `viewport_v1`)? This single answer unblocks the repo-wide test problem.
3. **Playground status:** Is `playground/` a *research host* or the *de facto application*? The answer determines whether it may depend on experiments, whether its input map may diverge from production, and whether `tests/test_playground_transformer.py` belongs in `tests/`.
4. **Load-bearing experiments (D3):** Where should the OBJ loader, camera framing helper and head asset live if the Integration Lab and the rigging experiment are ever treated as disposable?
5. **Test trust set (T1/T2/T6):** Which trees must be green, and under which single command? Should a `pytest.ini`/`pyproject.toml` define `testpaths` and rootdir, and what is the authoritative number (398? 398+233? +experiment suites)?
6. **Legacy items:** Were `tests/mesh.py`, `tests/history.py`, `tests/operations_init.py`, `tests/mnt/**`, `tests/*.patch` and `playground/experiments/articulation/_old_/` intentionally kept, or are they awaiting removal as WP-04 recommended? (Do not delete before an explicit answer.)
7. **`add_edge` (D6):** Should `CORE_V1_FREEZE.md §7.1` be amended, or does ROADMAP §13 supersede it as the current record? Two documents currently imply different procedures.
8. **Documentation authority (drift rows 1, 2, 9, 10, 11):** Which of the two `CORE_ARCHITECTURE_REASSESSMENT` copies and which WP-01A/WP-02 revisions are canonical? Is the reconciliation audit §A.1 still SSOT, or historical evidence that should be archived and referenced as such?

**No files were created, modified, renamed or deleted during this audit; the working tree is unchanged.**