# WP-SYM-LAB-03 — Rebase the Symmetry Lab onto the Production app (PLAN)

**Type:** B (research / plan) · **Mode (M5):** Discovery · **Date:** 2026-10-03
**Status:** PLAN, nothing decided or built. The target below is a proposal to evaluate.
**Base:** `main` @ `f15957c` (WP-SYM-LAB-02 S2).
**Trigger:** Artist (Manu, 2026-10-03): Symmetry need not reach Production fast, but it must
use the Production tools. A Lab with its own renderer makes no sense long-term.
**Code changes in this package:** none.

Related: [Lab README](../../experiments/symmetry_lab/README.md) (current state, verdicts,
colour legend) · handoffs [Slice 2](WP-SYM-LAB-01_SLICE2_CLAUDE_CODE_HANDOFF.md) …
[Slice 7](WP-SYM-LAB-01_SLICE7_CLAUDE_CODE_HANDOFF.md) ·
[AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md) ·
[AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md) ·
[AD-013](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md) ·
[ROADMAP §7, entry 2026-10-02](ROADMAP.md) (Symmetry promotion check) ·
[Symmetry Evolution Research](../research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md) §12.

---

## 0. Summary

- **The target works.** The Lab can become a thin `experiments/` entry point that builds the
  same `Application` → `Viewport` V02 → `GLRenderStore` path as `src/main.py` and adds only
  symmetry. That needs **four small hooks, one bug guard and one pure refactor in `src/`**
  (§3). It needs **no `src/core` change**, and `src/main.py` behaves exactly as before
  (every hook defaults to "off").
- **Exactly one hook is an architecture boundary:** H2, letting an experiment handle input
  before `Application` does. It touches AD-013 I3/I4 (input authority). Per AGENTS.md §5 it
  needs a short AD-013 addendum before code. That is a technical decision, not an Artist
  question.
- **Most of the Lab is already in the app or is a stale copy.** Of 34 inventoried Lab
  features: **12 are already in the app (a)**, **13 are symmetry-only and get re-hosted (b)**,
  and **9 are obsolete copies to delete (c)** (§2). Symmetric W/E/R already run in
  `src` (`MoveTool`/`TransformTool` read `mesh.symmetry_definition`), so they work in the
  rebased Lab for free, with the app's constraints.
- **Three findings this plan surfaced** (not in the trigger list):
  1. `Application._transform_step` does not catch `SeamConstraintError`, so E/R on a seam
     vertex would raise out of the event handler once symmetry is on (the Lab catches it
     itself today).
  2. A Lab history entry pushed past `Application` desynchronises the Undo/Redo selection
     mirror.
  3. The app's contextual C and Knife run one-sided under symmetry. This makes the pending
     E5 test real again.
- **Tests:** of 263 Lab tests, about 133 are kept or ported to the `Application` path and
  about 130 are deleted with the copies they test (§4.4).
- **Visible changes that need a new Artist verdict: two** (§4.3). One is a question (Q1,
  shading of `subd_cube`). The other is a single combined re-check session after Slice 4.

---

## 1. Repository reality (verified 2026-10-03)

### 1.1 What the Lab is today

`experiments/symmetry_lab/`: 16 modules, 263 tests (14 files). The Lab builds a Production
`Application` (scene, selection, history, camera, bindings, tool manager). Everything
between the pyglet event and the tool is its own code:

```
pyglet event → mirai.pyglet_input → LabDispatcher (own gestures, own Move arming, own Knife)
            → LabRenderer (own shaders, own VBO data) — no Viewport, no GLRenderStore
```

Test baseline in this container: `pytest experiments/symmetry_lab/tests` → 253 passed. 10 need
EGL, which this container lacks: `test_input_path.py` (8), `test_import_boundary.py` (1) and
`test_lab_knife_window.py::test_enter_has_no_lab_input` (1). This is an environment
limit, not a regression (the same tests run with a display).

### 1.2 Drift evidence

| # | Drift | Where | Effect |
|---|---|---|---|
| D1 | W ignores constraints | `lab_dispatch.py:602` passes `space` only for Rotate/Scale; the app passes it for all three (`application.py:1103`, B4.1) | X/Y/Z does nothing for W in the Lab, but does in the app |
| D2 | Mirrored Knife is a pre-B7 copy | `lab_knife.py` (incremental, real cut per click) vs. `mirai.topology.knife` (virtual path, cut at commit, S1 resolver, S4 planner) | Not promotable; every Knife iteration since B7 is missing |
| D3 | Knife picking is a pre-B7 Playground copy | `lab_knife_pick.py` (83 lines, from `playground/…/knife_pick.py` @ `649fff5`) vs. `mirai.topology.knife_pick` (272 lines) | Lab Knife hover diverges from the app |
| D4 | Renderer and draw data are copies | `lab_render.py` ← `playground/window.py`, `lab_draw_data.py` ← `playground/vbo_builder.py` | No display modes, no occlusion picking, no flat shading |
| D5 | Lab triangulation is behind `src` for n-gons | `lab_draw_data.py:138` falls back to `triangulate_face(boundary)` **without positions** = plain fan; `src` ear-clips concave n-gons (`viewport/derived.py:105`) | Concave faces after a cut draw wrong in the Lab |
| D6 | E10 Newell normals duplicated | `lab_draw_data.face_normals` vs. `viewport.derived.face_normal` (in `src` since `e64de4f`, same scheme: Newell face normal, vertex normal = normalised sum) | Obsolete copy |
| D7 | Input logic re-implemented | `LabDispatcher` (725 lines): gestures, click threshold, hold-key arming, hover, undo; the app has `PointerGestures` (AD-019), `_transform_arm`, hover via `pick_component` + `PickCache` (B8) | Each app fix (UX2b Shift tracking, `on_deactivate`, B8 occlusion) needs a Lab copy |
| D8 | Undo semantics differ | Lab clears the selection after Undo (`lab_dispatch.py:381`); the app restores it (B6 follow-up, Artist 2026-09-28) | Different behaviour for the same keys |
| D9 | Stale record | ROADMAP §7 2026-10-02 (a) says only `MoveOperation` supports symmetry; since S2 (`f15957c`) Rotate/Scale do too (`core/operations/transform.py:323`) | Record only; corrected in ROADMAP §7, entry 2026-10-03 |

### 1.3 Production facts the rebase depends on

- **Symmetric W/E/R already live in `src`.** `MoveTool` (`tools/move.py:193`) and
  `TransformTool` (`tools/transform.py:360`, `resolve_symmetry`) read the definition from the
  mesh. `Application` needs no symmetry knowledge for them.
- **`SeamConstraintError` is not handled by `Application`.**
  `TransformTool.begin` raises it (`tools/transform.py:375–388`). `_transform_step` calls
  `begin_current_interaction` without a guard (`application.py:1103`). This is unreachable
  from `src/main.py` (it never sets a definition) but reachable in any host that does.
- **Selection mirror stack.** `Application` pairs every `history.push()` *it* triggers with a
  selection snapshot (`_record_selection_history`, `application.py:1240`) and pops both
  LIFO on Undo/Redo (`_apply_undo_redo`, `:1183`). A push from outside desynchronises this.
  Concrete case: W commit, then Shift+S (Lab push), then Ctrl+Z undoes the symmetry step but
  restores W's *before*-selection. The docstring anticipates exactly this case ("ein
  künftiger Push-Pfad, der hier noch nicht verdrahtet ist").
- **Topology tools carry no symmetry declaration.** `supports_symmetry` exists only on
  `Operation` (`core/operation.py:88`). Split/Connect/Knife are `MeshStateCommand`
  compositions, not Operations, so they run one-sided under symmetry. A dead seam edge
  degrades visibly, without a crash (`mirai.symmetry._seam_vertex_ids` skips invalid IDs, and
  the new seam vertex shows as `UNPAIRED`). This is the P1/P2 situation from Slice 6.
- **Overlay precedent.** `viewport.overlay.TOOL_LAYERS` plus `Viewport.set_tool_overlay`
  (B7): ready-made positions from the caller; the Viewport knows no Knife.
  `gl_line_overlay.FlatColorLayers` already takes `LAYERS`/`LAYER_STYLES` as class
  attributes (subclassable). `GLPointOverlay` does not (`DRAW_ORDER`/`LAYER_STYLES` are
  module constants, `gl_point_overlay.py:51,58`).
- **Cost of the symmetry report** (container, not reference hardware): `symmetry_report`
  takes 0.2 / 2.0 / 6.3 ms on `subd_cube` / `head_basemesh` / `man_with_shoes_basemesh`;
  `topology_report` takes 0.3 / 3.4 / 9.8 ms. Per frame is too expensive; per change matches
  today's Lab (§3, H1).

---

## 2. Deliverable 1 — Inventory

(a) = already in the app · (b) = symmetry feature, re-host · (c) = obsolete copy, delete.
Verdicts are quoted from the Lab README; none of them changes here.

| # | Lab feature (origin) | Module | Class | Production counterpart / re-host note | Artist verdict |
|---|---|---|---|---|---|
| 1 | Window, event translation (S2) | `lab_window.py` | c | `src/main.py` wiring, made importable (H6) | Slice 2 checked 2026-09-24 |
| 2 | Shaders, mesh draw (S2) | `lab_render.py` | c | `Viewport` → `GLRenderStore`, line/point/triangle overlays | Slice 2 checked |
| 3 | Face/edge/vertex/highlight VBO data (S2) | `lab_draw_data.py` (`face_data`, `edge_data`, `vertex_data`, `highlight_data`) | c | `RenderMesh`, `wireframe.edge_segments`, `SelectionOverlay` | Slice 2 checked |
| 4 | E10 Newell face/vertex normals (S4) | `lab_draw_data.py` (`face_normals`, `vertex_normals`) | c | `viewport.derived.face_normal` since `e64de4f` (same scheme) | part of Slice 4 KEEP |
| 5 | E10 quad split at the shorter diagonal (S4) | `lab_draw_data.triangulate_face_symmetric` | c (open) | `src` keeps the fan for convex quads. Not re-hosted: picking (B8 occlusion) and face overlays use `src` triangulation, so a Lab-only draw split would make the drawn and the picked surface disagree. Visible on `subd_cube` only (24/24 mirrored quads asymmetric; `head_basemesh` 0/324) → **Q1** | Slice 4 KEEP, step 10 |
| 6 | Orbit/Pan/Zoom with Lab overrides Alt+LMB, Shift+LMB, MMB, RMB unbound (S2) | `lab_bindings.py`, `lab_dispatch.py` | a | App bindings (Artist Input Truth, WP-06 B2): Alt+LMB drag, Alt+Shift+LMB drag, wheel | Slice 2 checked |
| 7 | Vertex click select, replace only (S2) | `lab_dispatch.select_at` | a | `Application.select_at` (replace/add/remove/toggle, V/E/F modes) | Slice 2 checked |
| 8 | Asset by registry name, framing (S2) | `lab_scene.py` | a (+ thin b) | `init_scene("obj", obj_path=asset_path(name))` + `frame_scene()`; the registry-name CLI with exit code 2 stays in the Lab | — |
| 9 | Lab binding context, `LAB_OVERRIDES`, console listing (S2–S7) | `lab_bindings.py`, `run.py` | b | Shrinks to Shift+S, M, Shift+B (navigation and C overrides dropped); console listing kept (AD-013 I6) | — |
| 10 | Symmetry cycle Shift+S off→X→Y→Z→off, E1–E3, one undo step each (S3) | `lab_symmetry.cycle_symmetry` | b | Via H2 (key) + H3 (history with selection mirror) | Slice 3 KEEP |
| 11 | Plane outline (S3) | `lab_draw_data.plane_outline_data` | b | Lab line overlay via H1 | Slice 3 KEEP |
| 12 | State markers: seam green, unpaired magenta, ambiguous white; `SymmetryReport` (S3) | `lab_symmetry.symmetry_report`, renderer | b | Lab point overlay via H1 | Slice 3 KEEP |
| 13 | Mirrored partner of the selection, turquoise (S3) | renderer + `mirrored_selection` | b | Lab point overlay via H1 | Slice 3 KEEP |
| 14 | Hover vertex (S4) | `lab_dispatch._update_hover` | a | App hover (B2b, `selection.hovered`, occlusion-aware B8) | Slice 4 KEEP |
| 15 | Mirrored partner of the hover, turquoise (S4) | renderer | b | Lab point overlay via H1, reads `selection.hovered` | Slice 4 KEEP |
| 16 | Move target rule: selection else hover, fixed at key press, hover target leaves the selection empty (S4 A4/E7/E8) | `lab_dispatch._arm_move` | a | `Application._transform_arm` (B3), same rule | Slice 4 KEEP |
| 17 | W hold-key-hover gesture (2026-09-27) | `lab_dispatch` | a | `Application.key_press`/`pointer_motion`/`key_release` (B3, `PROMOTED`) | **pending** → superseded (§4.2) |
| 18 | Symmetric Move semantics (partner mirrored, seam slides in plane) | `src` `MoveTool`/`MoveOperation` | a | Unchanged; the Lab's own arming code goes | Slice 3 KEEP |
| 19 | Symmetric Rotate/Scale + pivot = selection ∪ partners (WP-SYM-LAB-02 S2) | `src` `TransformTool`, `resolve_symmetry` | a | Unchanged | **pending** (S2) |
| 20 | Constraint keys X/Y/Z, Shift+X/Y/Z as a toggle (S2) | `lab_dispatch._toggle_constraint` | a | `Application._constrain` (B4.1); now also applies to W (D1) | (part of S2, pending) |
| 21 | Seam refusal shown before the first motion | `lab_dispatch.py:608` | a after H5 | `Application._transform_step` + H5 | (part of S2, pending) |
| 22 | E5 gate MARK/BLOCK, Shift+B, reads `supports_symmetry` (WP-SYM-LAB-02 S1) | `lab_dispatch._gated`, `_arm_move` | b | Via H2; extended to C (contextual C + Knife), which has no declaration and so counts as unsupported | **pending** (E5) |
| 23 | Re-Symmetrize plan/apply, topological source side (S5) | `lab_resymmetrize.py` | b | Unchanged module; push via H3 | Slice 5 KEEP |
| 24 | Re-Symmetrize preview: modal M/M/Esc, blue/light green/light red + lines, text line, hover paused, other commands ignored with a hint (S5) | `lab_dispatch` preview code, renderer | b | Via H2 (key, click, motion) + H1 + Lab HUD | Slice 5 KEEP |
| 25 | Topological pairing and sides (S5, E11/E12) | `lab_topology.py` | b | Unchanged module | Slice 5 KEEP |
| 26 | Undo/Redo clears the selection | `lab_dispatch._undo_redo` | a | App restores the selection (B6 follow-up) | — |
| 27 | Status line text, on screen (S3–S7) | `lab_status.py`, `lab_window` labels | b | Lab HUD (pyglet label) = Lab state line + `app.status_message`; writes via H4 | — |
| 28 | Esc closes the window when idle (S2/S3) | `lab_window` | a | App rule: Esc = Cancel only, the X button closes (B1 A3) | Slice 3 KEEP step 8 (covered by app decision) |
| 29 | Mirrored Knife engine, intent pairs, validation E16–E22 (S6) | `lab_knife.py` | c | **Not re-hosted** (pre-B7 copy, D2). A future symmetric One Knife mirrors the virtual path before resolution (separate package). Findings P1–P3 are kept as tests (§4.4) | Slice 6: headless only, never verdicted |
| 30 | Knife picking (S7) | `lab_knife_pick.py` | c | `mirai.topology.knife_pick` | Slice 7 **pending** → moot |
| 31 | Knife hover dry run, Knife markers, Knife status (S7) | `lab_knife_preview.py`, `knife_preview_data`, `knife_text` | c | — | Slice 7 **pending** → moot |
| 32 | `Change` flags, `take_changes`, full VBO rebuild | `lab_dispatch.Change`, `lab_window._sync` | c | Viewport dirty flags; the Lab overlay re-syncs on the Viewport's notifications (H1) | — |
| 33 | No `playground/` import (AD-010 precedent) | `tests/test_import_boundary.py` | b | Kept; the module list shrinks | — |
| 34 | `sys.path` bootstrap | `_paths.py` | b | Kept, minimal | — |

---

## 3. Deliverable 2 — Hook points in `src/`

Smallest set found: H1–H4 are hooks, H5 is a bug guard, H6 is a pure refactor. All six are
off by default, and `src/main.py` uses none of the hooks.

| Hook | What (smallest form) | Needed by | Classification (AGENTS.md §5) |
|---|---|---|---|
| **H1** Extra overlay | `Viewport.add_overlay(o)`. `o.sync(mesh, selection)` runs inside `Viewport.sync()` whenever the Viewport's own selection/geometry/topology dirty flags were set, or when `o.dirty` is set. `o.draw(camera_uniforms)` runs in `render()` **after the tool lines, before the point overlay**. Plus: `GLPointOverlay` takes its layers/styles as class attributes, like `FlatColorLayers`, so the Lab can subclass it | Inventory #11–13, 15, 24 | **Small detail.** Precedents: `TOOL_LAYERS`/`set_tool_overlay` (B7) and `FlatColorLayers`. The Viewport stays symmetry-agnostic, data still flows Core → Viewport, and there are no new colours in `src` |
| **H2** Input hook | `Application.input_hook` (default `None`), consulted first at three call sites: `key_press(input) → consumed?` (`application.py:993`), `click(command, x, y) → consumed?` in `_execute_click` (`:1440`, after `PointerGestures` decided click vs. drag), `pointer_motion(x, y) → consumed?` (`:1345`). The hook resolves its own commands through the one `app.bindings` with its context (`symmetry_lab`) | #10, 22, 24, Slice 1 C refusal | **Architecture boundary.** A second interaction authority inside the app's input path touches AD-013 I3 (one authority owns start and end) and I4 (one binding authority), plus AD-015/AD-016 input ownership. Needs an AD-013 addendum (problem, the alternatives below, decision) **before** code. Not an Artist question |
| **H3** External mesh change | `Application.record_mesh_change(command, selection_before, moved=None)`: `history.push`, `_record_selection_history`, pick cache invalidate, `viewport.on_vertices_moved(moved)` or `on_topology_changed()`, `_refresh_hover()`. The Lab functions return their `MeshStateCommand` instead of pushing it (`lab_symmetry.py:88`, `lab_resymmetrize.py:166`) | #10, 23 | **Small detail.** Completes the push path the B6 follow-up docstring anticipates; `HistoryStack` and core stay unchanged |
| **H4** Status | `Application.set_status(message)`, the public form of `_set_status` (`:1278`), same `status_serial` | #22, 24, 27 | **Small detail** |
| **H5** Seam refusal guard | `_transform_step`: catch `SeamConstraintError` from `begin_current_interaction`, end the transform, status `"<Rotate/Scale>: refused — <reason>"`, `_refresh_hover()`. No history entry | #21; reachable as soon as Slice 1 sets a definition | **Small detail.** Bug guard for a refusal AD-SYM-02 §2.4 / INV-8 already decided; status text `PROVISIONAL` like the other app status lines |
| **H6** Importable entry wiring | Split `src/main.py` into `create_window()`, `install_handlers(window, app)` and `run(window, app)` (plus the `gl_types` constant); `main()` composes them. Behaviour identical | #1 | **Small detail.** Pure refactor; it also makes the wiring headless-testable for the first time (`tests/test_main_entry_point.py` only covers the draw path) |

The Lab draws its HUD with its own `on_draw` handler pushed on top of the shared one. It
calls the app's draw first and then its label. That is Lab code, not a hook.

### 3.1 Alternatives considered

**Overall approach**

- **Keep the Lab renderer, import instead of copy** (replace D3–D6 with `src` imports, keep
  `LabDispatcher`). *Not used because* the root cause is D7: a second input layer goes on
  drifting from the app (D1 and D8 are input drift, not draw drift).
- **Promote the symmetry UX into `src/main.py` behind a flag.** *Not used because* of M3 and
  AD-013 I7: promotion is the Artist's decision (deferred, ROADMAP 2026-10-02). The trigger
  explicitly keeps `src/main.py` free of symmetry UX.
- **A general plugin/extension system in `Application`** (command registry, overlay
  providers, event bus). *Not used because* of AGENTS.md §7 ("do not build future systems")
  and INPUT_COMMAND_TOOL_CONTRACT §3 ("must not introduce a complex hierarchical context
  framework without a demonstrated use case"). One experiment is one use case, so it gets one
  hook object with three call sites and no registry.

**H2 input hook**

- **Subclass `Application` in the Lab and override `key_press`, `_execute_click`,
  `pointer_motion`.** *Not used because* it couples the experiment to private methods.
  An `Application` refactor would change Lab behaviour without any signal, which is the same
  drift class in disguise and a fork of the interaction authority (AD-013 I1/I3).
- **A facade in front of `Application` at window level.** *Not used because* blocking a
  select click but not an Alt+LMB orbit needs the click-vs-drag decision.
  `PointerGestures` makes that decision inside `Application`, so a facade would have to
  re-implement it, which is the `LabDispatcher` problem again. Keys alone would work this way;
  pointers would not.
- **Fallback-only: Application resolves an "active context" and hands unknown commands to
  the Lab.** *Not used because* it cannot pre-empt anything. The C refusal, the E5 BLOCK and
  the modal Re-Symmetrize preview all have to stop an app command, not just add new ones.

**H1 overlay**

- **Symmetry layer names and colours in `src/viewport`.** *Not used because* the Lab colour
  legend would become Production UX (M3, AD-013 I7).
- **The Lab draws its overlays itself after `viewport.render()`.** *Not used because* of draw
  order: the seam/partner markers would cover the selection and hover points. In the Lab the
  selection is drawn last (README, "Zeichenreihenfolge"); in the app the point overlay is the
  last pass.
- **Recompute the overlays every frame** (no `sync` notification). *Not used because* it costs
  6–10 ms per frame on `man_with_shoes_basemesh` (§1.3). Driving it off the Viewport's
  notifications costs the same as today's Lab (one report per change) and covers app-driven
  changes too (Undo, drag, Knife commit), which `Application` already reports to the Viewport.

**H3 history**

- **The Lab pushes directly and accepts the desync.** *Not used because* Undo would restore a
  wrong selection (§1.3, concrete case).
- **The Lab clears the selection after every Undo, as today.** *Not used because* it fights the
  app's restore (D8) and drops an Artist decision (B6 follow-up).

**H6 entry**

- **Copy the ~100 lines of `src/main.py` handlers into the Lab.** *Not used because* this is the
  drift D4/D7 again. The Shift tracking (UX2b) and `on_deactivate` were added to `main.py` on
  2026-10-02, exactly the kind of change a copy misses.
- **Call `main.main()` with injected hooks.** *Not used because* `main.py` would then have to
  know about experiments.

### 3.2 Not needed

No `src/core` change, no new command in `mirai.interaction.commands` (`SymmetryCycle`,
`ReSymmetrize`, `SymmetryGateMode` stay Lab-local, as the test does today), and no
`_VALID_CONTEXTS` change (`set_default` takes any context string; only `keymap.json` is
restricted, and the Lab does not use it).

---

## 4. Deliverable 3 — Verdict preservation

### 4.1 KEEP behaviours reproduced exactly

| KEEP (date) | Behaviour | Provided by after the rebase | Proven by |
|---|---|---|---|
| S3 (2026-09-25) | Shift+S off→X→Y→Z→off; one undo step each; Ctrl+Z/Ctrl+Y walk the cycle | Lab via H2 + H3 | ported `test_lab_symmetry` cycle tests + new mirror-alignment test (W commit → Shift+S → Undo ×2 restores the right selection each time) |
| S3 | Plane outline through the origin, bounds + 10 %, light blue | Lab overlay (H1) | kept `plane_outline` tests |
| S3 | Seam green, unpaired magenta, ambiguous white; `Symmetrie: X (valid) \| ohne Partner: N`; `man_with_shoes` X = 54 unpaired | Lab overlay + HUD | kept asset characterisation |
| S3 | Selected vertex shows its mirrored partner in turquoise | Lab overlay | new overlay-data test |
| S3 | W moves vertex and partner mirrored; a seam vertex slides in the plane; one undo step; Esc restores exactly without history | `src` `MoveTool` through `Application` | ported `test_lab_move` symmetric subset |
| S4 | Hover shows the mirrored partner in turquoise without selecting | Lab overlay reading `selection.hovered` | new overlay-data test |
| S4 | Move target rule A4/E7/E8 | `Application._transform_arm` (same rule) | app tests (`test_application_move`, `test_application_hover`) |
| S5 | M preview → M execute (one undo step; 0 changes = no entry) → Esc closes without change | Lab via H2 + H3 | ported dispatcher-level `test_lab_resymmetrize` |
| S5 | Source side is topological (A6); exactly one vertex; the five rejections | `lab_resymmetrize` (unchanged) | kept pure tests |
| S5 | During the preview: navigation works; select, W/E/R, Shift+S, C, Undo/Redo ignored with `Vorschau aktiv — Befehl ignoriert`; hover paused | H2 key + click + motion | ported preview tests |
| S5 | Preview colours blue / light green / light red with lines; text line above the status line | Lab overlay + HUD | kept `test_preview_draw_data` |
| S5 | Selection kept after execute | H3 (selection snapshot) | ported |

### 4.2 Pending verdicts

| Pending | After the rebase |
|---|---|
| W like the app (2026-09-27) | **Superseded, never verdicted.** The Lab *is* the app's W (B3 `PROMOTED`); there is nothing Lab-specific left to judge |
| Slice 7 mirrored Knife in the window | **Moot, never verdicted.** Not re-hosted (trigger). Findings E23–E30, P1–P3 stay in the Lab README as research for the symmetric One Knife |
| WP-SYM-LAB-02 S2 (symmetric Rotate/Scale, pivot) | **Still open.** Same `src` code; the test steps re-run in the rebased Lab. README step 5 (select both vertices of a pair) becomes clickable (Shift+click) |
| E5 MARK vs. BLOCK | **Still open, testable again.** With the mirrored Knife gone, C (Split/Connect/Knife) is the real "unsupported tool". MARK runs it one-sided and the seam degradation is visible (magenta / `partial`); BLOCK refuses |

### 4.3 What visibly changes

**Covered by existing app decisions: no new verdict** (the rebase adopts the app; it decides
nothing new):

| Change | App decision |
|---|---|
| Selection yellow 8 px instead of red 10 px; hover pale translucent yellow; no orange dot per vertex | B2b (A10/A11) |
| Navigation: Alt+Shift+LMB drag = Pan, Shift+click = add to selection, MMB unbound, no RMB rule | B2 (Artist Input Truth) |
| Picking is occlusion-aware in Shaded (back-side vertices not pickable); hover cleared during orbit | B8, B2b |
| W honours X/Y/Z (was ignored, D1) | B4.1 |
| Undo/Redo restores the selection instead of clearing it | B6 follow-up |
| Esc never closes the window; the X button does | B1 A3 |
| V/E/F modes, D display modes, contextual C, Knife available | B5a, B5b, B6, B7 |
| C under symmetry: no mirrored cut any more (Slice 1: refused; Slice 4: E5 MARK/BLOCK) | Trigger: the mirrored Knife is not re-hosted |
| Status mixes app English and Lab German texts | Not a product question; Lab strings stay as written |

**Needs a new Artist verdict (short on purpose):**

1. **Q1 — Shading of `subd_cube` under X symmetry** (Slice 4 KEEP, step 10). Without E10's
   diagonal rule the cube shades asymmetrically again; the head does not change. See §6.
2. **One combined re-check session after Slice 4** (old and new Lab side by side, about
   10 minutes): S3–S5 KEEP smoke in the new host + the pending S2 + E5 with C + Q1. This is not
   a new decision on any KEEP. The Artist only confirms "the same as before", which no test
   can prove.

### 4.4 Test porting plan (263 tests)

| File | Tests | Keep | Port to the `Application` path | Delete | Note |
|---|---|---|---|---|---|
| `test_lab_topology.py` | 19 | 19 | – | – | unchanged module |
| `test_lab_symmetry.py` | 20 | 17 | 3 | – | cycle tests via H2/H3; + new mirror-alignment test |
| `test_lab_resymmetrize.py` | 30 | 17 | 13 | – | dispatcher tests → `app.key_press` / `pointer_*` |
| `test_lab_symmetric_transform.py` | 12 | – | 12 | – | through `app.key_press`/`pointer_motion`; + W with constraint under symmetry |
| `test_lab_gate.py` | 13 | – | 13 | – | E5 via H2; + C under MARK/BLOCK |
| `test_lab_scene.py` | 7 | – | 7 | – | `init_scene("obj", asset_path(…))` |
| `test_lab_move.py` | 26 | – | ≈6 | ≈20 | keep: symmetric partner, seam slide, one undo step, exact Esc, no-symmetry case, status; gesture mechanics are app-tested |
| `test_lab_knife.py` | 36 | 12 | – | 24 | keep baseline + P1–P3 (Mesh primitives + `lab_topology`; inline the 2–3 helpers); engine tests go with the engine |
| `test_lab_bindings.py` | 20 | – | ≈8 | ≈12 | Shift+S/M/Shift+B + global fall-through; nav/C overrides gone |
| `test_draw_data.py` | 9 | 1 | 4 | 4 | diagonal characterisation (2) and mirrored normals (2) against `viewport.derived`; VBO lengths deleted |
| `test_import_boundary.py` | 1 | 1 | – | – | module list updated |
| `test_lab_hover.py` | 11 | – | – | 11 | all are app rules (B3/E24); a hover-partner test is new |
| `test_lab_dispatch.py` | 11 | – | – | 11 | navigation/select = app (`test_application_pointer`) |
| `test_input_path.py` | 8 | – | – | 8 | pyglet → `Input` is `tests/test_pyglet_input.py` |
| `test_lab_knife_window.py` | 40 | – | – | 40 | Knife window not re-hosted |
| **Total** | **263** | **67** | **≈66** | **≈130** | |

New tests in `tests/` (Production): H1 (draw order, `sync` on notifications, no-op without
overlays), H2 (`None` = identical behaviour; consume/pass for key, click, motion), H3 (mirror
alignment), H4, H5 (refusal: no history entry, transform ended, status), H6 (`install_handlers`
headless) and **symmetric Move with an axis constraint**. That combination is untested in
`src` today (`tests/test_symmetric_move.py` has no `space` case) and becomes reachable by D1.
A guard test asserts that `src/main.py` sets no `input_hook` and adds no overlay.

---

## 5. Deliverable 4 — Slice plan

The new host is built **next to** the old Lab, in the same package with a new entry
(`run_app.py`), until the Artist session. That keeps the pending S2/E5 tests playable at every
point and allows an old-vs-new comparison. Each slice is one revertable commit series;
`src` changes come first and are behaviour-neutral for `src/main.py`.

| Slice | Scope | `src` touched | Done when |
|---|---|---|---|
| **1** App path + cycle + plane/state overlays | Step 0: AD-013 addendum for H2 (from §3.1). `src`: H6, H1, H2 (key call site only), H3, H5. Lab: `run_app.py` builds the app path with registry assets; Shift+S via H2/H3; plane outline + seam/unpaired/ambiguous markers via H1; HUD with the symmetry state. **C is refused while symmetry is on** (fixed, `Symmetrie aktiv — C spiegelt nicht`), because without it C would run one-sided without warning (INV-8); Slice 4 replaces this with the E5 gate. Symmetric W/E/R work from here on through `src`; no Lab code for them | `src/main.py` (refactor), new `src/app_window.py` (or similar), `viewport/viewport.py`, `viewport/gl_point_overlay.py`, `mirai/application.py` | `pytest tests` and `playground/tests` unchanged except the new hook tests; ported cycle/outline/asset tests green; `src/main.py` guard test green |
| **2** Mirrored previews + HUD | Partner markers for selection and hover (vertex mode); HUD line as `lab_status` (state, unpaired count, target, constraint); H4 | `application.py` (H4) | ported symmetric move/transform tests via `Application`; new W + constraint + symmetry test |
| **3** Re-Symmetrize | M preview/execute/Esc via H2 (add the click + motion call sites), H3 with moved IDs; preview overlay and text line; hover paused | `application.py` (H2 call sites) | all 30 resymmetrize tests (kept or ported) green |
| **4** E5 gate | Shift+B MARK/BLOCK via H2, now for W/E/R (`supports_symmetry`) **and C** (no declaration = unsupported); replaces the Slice 1 refusal; MARK keeps a persistent HUD line while a one-sided C/Knife session runs | — | ported gate tests + C cases (MARK: one-sided, one history entry, seam degradation visible; BLOCK: nothing, no history). **Then the Artist session (§4.3).** |
| **5** Swap and delete | `run.py` → app host; delete the (c) modules and their tests (§4.4); README rewritten (manual-test sections as history, new steps); ROADMAP §7 entry; W-like-app and Slice 7 marked superseded/moot | — | Lab tests ≈133 + new; no Lab module imports a deleted one; README legend matches the overlays |

**Not in any slice:** the mirrored Knife (a future symmetric One Knife is its own package:
mirror the virtual path before resolution, ROADMAP 2026-10-02 (b),
`docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md`), partner previews in edge/face
mode, Extrude/Loop Insert, any Playground change, any new symmetry capability.

**Revert path:** Slices 1–4 add files and default-off hooks; reverting a slice restores the
previous state, and the old `run.py` keeps working until Slice 5. Slice 5 is only deletions
plus docs.

**Test command for later `src` changes:** once Slice 1 lands, changes to `mirai/application.py`
or `src/viewport/` should also run `pytest experiments/symmetry_lab/tests` (proposed CLAUDE.md
addition in Slice 1). The Lab then catches Production changes instead of drifting from them,
which is the point of the rebase.

---

## 6. Deliverable 5 — Open questions for the Artist (M4-filtered)

**Q1 (Product Truth / Priority) — symmetric shading of `subd_cube`.** In the Slice 4 KEEP
(step 10) the Lab split quads at the shorter diagonal, so `subd_cube` shaded the same left and
right. The rebased Lab draws with Production's split, which is asymmetric on `subd_cube` (24
of 24 mirrored quads) and identical on `head_basemesh` (0 of 324). Choose one:
(a) accept it in the Lab for now and raise it again when Symmetry is promoted;
(b) make "shorter diagonal" Production's quad split, a separate small package that changes
the shading of every quad in `src/main.py` (and its picking/face overlays, which use the same
split).
*Agent recommendation:* (a). The head, the main asset, is unaffected.
*Prepared test:* in the session after Slice 4,
`python experiments/symmetry_lab/run.py` vs. `python experiments/symmetry_lab/run_app.py`,
both `subd_cube`, Shift+S → X, orbit to compare the left and right shading.

**Not asked (decided by the agent under the filter):**

- the hook design and the H2 addendum: technical, reviewable;
- building next to the old Lab vs. in place: technical;
- the default asset (`subd_cube` stays, matching the README steps);
- the status language: German Lab texts stay;
- C refused in Slice 1: follows INV-8 (decided);
- E5 now covering C: re-hosting the existing gate onto the real tool set, E5 itself stays the
  Artist's question;
- whether W-like-app and Slice 7 need verdicts: recorded as superseded/moot, not as
  validated (M3: no agent claims validation).

---

## 7. Risks

- **R1 — the hook grows into a plugin system.** Guard: one hook object, three call sites,
  documented as experiment-only in the AD-013 addendum; a second user needs its own decision.
- **R2 — Lab tests break on Production changes.** Intended: that is the signal the drift lacked
  (§5, test command).
- **R3 — cost per change.** `symmetry_report` 6 ms + `topology_report` 10 ms on
  `man_with_shoes` (container). It runs per change, not per frame; `topology_report` runs only
  while the Re-Symmetrize preview is open. This matches today's Lab; to re-measure on the
  reference PC if a drag feels slow.
- **R4 — the Slice 1 C refusal is visible only as a status line.** Accepted until Slice 4;
  the old Lab stays available for comparison.

---

## 8. Docs to update when the slices land

Lab README (structure, controls table, legend, manual-test sections; the old sections stay as
history), this plan (status per slice), AD-013 (addendum, Slice 1),
`src/main.py` docstring (H6), ROADMAP §7 (one dated entry per slice),
CLAUDE.md (Lab test command, Slice 1).
