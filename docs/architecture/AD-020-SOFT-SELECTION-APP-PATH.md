# AD-020 — Soft Selection on the Production App Path (S2 host, Core seam, controls)

**Status:** **PROPOSED** (2026-10-10). Manu decides after an independent review (§13).
**Mode (M5):** Discovery, decision preparation. No implementation, no code, test or binding change.
**Work package:** WP-SOFT-01 gate between S1 (headless experiment, done) and S2 (first Artist test in the
Production window).
**Read at:** `main` @ `f65d223`. The handoff's baseline is `eaf43a3`; the delta was checked and contradicts
neither FINDINGS nor the handoff (§0.2).
**Basis (binding, only linked):** [`experiments/soft_selection/FINDINGS.md`](../../experiments/soft_selection/FINDINGS.md)
(cited as **FINDINGS**, observation IDs N/R/M/C/S/B/L as there),
[`README.md`](../../experiments/soft_selection/README.md), `influence.py`, `weighted_ops.py` of the same experiment;
[CORE_V1_FREEZE](CORE_V1_FREEZE.md), [AD-014](AD-014_Core-Change-Basis-Parameter-for-ScaleOperation.md),
[AD-013](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md) incl. Addendum H2 and the G-2 amendment,
[AD-016](AD-016-TRANSFORM-OWNS-QWE-SINGLE-CURRENT-TOOL.md), [AD-018](AD-018-PRODUCTION-DRAW-BINDING.md) §7,
[AD-019](AD-019-POINTER-CLICK-VS-DRAG-BINDINGS.md), [AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md)
(contact surface only), [V1_CORE](V1_CORE.md) §6, [V1_SPEC](../V1_SPEC.md) §2–§3,
[REFERENCE_HARDWARE](REFERENCE_HARDWARE.md).

**Question:** How does Soft Selection reach the Production app path (`src/main.py`) for a first Artist
comparison test (S2), and what does that cost in governance, Core and code?

**Evidence tags.** **[Code]** read in the repo at `f65d223` (file:line). **[FINDINGS]** an S1 observation.
**[Probe]** a scratch probe run for this AD in the container (not committed, §0.4, Appendix A/B).
*(Assumption)* not confirmed by Manu. *(Reading)* an interpretation, not a measurement. Everything in §2–§10
is a proposal and says what it rests on.

---

## Kurzfassung für Manu (Deutsch)

**Worum es geht.** Soft Selection soll für einen ersten Test (S2) ins echte Programm (`src/main.py`), nicht in
den Playground (deine Entscheidung vom 2026-10-08). Diese AD bereitet vier Entscheidungen vor; sie baut nichts.

**Empfehlung in einem Satz je Frage:**

1. **Wo läuft der Test?** Im normalen Programm, als `PROVISIONAL`-Fähigkeit, **standardmäßig aus**, mit einer
   Taste einschaltbar. Kein zweites Lab (das bräuchte einen neuen Eingriff in die Lab-Regeln von AD-013 und
   bringt nichts, was das Programm nicht schon kann).
2. **Muss der eingefrorene Core geändert werden?** **Nein, nicht für S2.** Die weichen Move/Rotate/Scale
   leben in `src/mirai` und nutzen nur die öffentlichen bzw. dokumentierten Erweiterungspunkte des Core.
   Eine Probe zeigt: das rechnet **bitgleich** wie das S1-Experiment und bei Radius 0 bitgleich wie der Core.
   Ob die Gewichtung später doch in den Core wandert, wird **nach deinem S2-Verdikt** in einer eigenen AD
   entschieden — vorher wäre es ein Core-Eingriff für etwas, das du noch nicht gesehen hast.
3. **Was siehst du?** Punkte in wenigen Farbbändern um die Auswahl (je wärmer, desto stärker geht der Vertex
   mit), dazu eine Statuszeile. Kein Einfärben der Fläche — das hattest du für die Auswahl schon abgelehnt
   („sieht aus wie Vertex Paint"); ob es für Soft Selection anders wäre, ist eine Frage an dich im Test.
4. **Tasten (Vorschlag, `PROVISIONAL`):** **O** = Soft an/aus · **Pfeil hoch/runter** = Radius eine Stufe
   größer/kleiner · **Shift+O** = Kurve (smooth ↔ linear) · **Ctrl+O** = Metrik (euclidean ↔ geodesic).
   Alle sind heute frei — im Programm, im Knife, im Symmetry Lab und in der Artist Input Truth. Sie wirken
   wie X/Y/Z: jederzeit umschaltbar, gelten ab der nächsten Geste. W/E/R halten bleibt wie es ist.

**Symmetrie:** Soft + Symmetrie wird **sichtbar abgelehnt** (W/E/R mit Soft an und Symmetrie an → Statuszeile,
nichts passiert). Im Symmetry Lab ändert sich sonst nur eine Kleinigkeit: die O-Tasten zählen dort als
„keine Operation" wie X/Y/Z, damit man Soft unter Symmetrie auch wieder ausschalten kann.

**Eine Messung vor deinem Praxistest.** Beim Ziehen bewegen sich mit Soft viel mehr Vertices (bis 112 am
Körper bei 30 %). Im Container kostet eine ganze Mausbewegung (Schritt + Viewport) dann bis ~2,5 ms
(Kanten aus) bzw. ~2,9 ms (Kanten an), fast alles im Viewport; auf deinem PC ist das grob 3–5× mehr, also
möglicherweise über der 8-ms-Schwelle (geschätzt, nicht gemessen). Deshalb: vor dem Praxistest ein Befehl
auf deinem PC, der genau das misst (wie die Probe im Symmetry Lab).

**Was du entscheidest (nach der Review):**
- Host: im Programm, aus per Default (A) — ja / anders?
- Core für S2 nicht anfassen (D) — ja / anders?
- Tastenvorschlag O, Pfeile, Shift+O, Ctrl+O — ok / andere Tasten?
- **Nicht jetzt:** Metrik, Kurve, Radius-Einheit und -Stufen, Scale-Formel — die entscheidest du im S2-Test,
  dafür ist er da.

---

## 0. Baseline, delta and scope

### 0.1 Test counts

Container (Linux, Python 3.13.16, `pytest` 9.1.1, `pyglet` 2.1.16, Xvfb + `libegl1`), at `f65d223`:

| Suite | Command | Result |
|---|---|---|
| Production | `xvfb-run -a pytest tests` | **2320 passed, 6 skipped** |
| Symmetry Lab | `xvfb-run -a pytest experiments/symmetry_lab/tests` | **466 passed, 4 skipped** |
| Soft Selection S1 | `pytest experiments/soft_selection/tests` | **96 passed** |

Without `libegl1` the Production suite reports 2232 passed, 41 skipped: the 35 extra skips are environment
skips (`Library "EGL" not found`) that the repo-root `conftest.py` turns into skips (CLAUDE.md § Testing). The numbers
above are with EGL installed; the remaining skips are the documented "no variant" cases of
`test_symmetric_removal.py` and its Lab counterpart.

The handoff's baseline (`eaf43a3`: 2028 passed, 6 skipped / 433 passed, 4 skipped / 96 passed) **does not
hold at `f65d223`**, and is not expected to: the commits since `eaf43a3` added the Production Extrude
(WP-06 B9), the symmetric Knife (AD-SYM-03 slices 6a–6c) and the symmetric Extrude (slice 7) with their tests
(`tests/test_application_extrude.py`, `test_extrude_tool_production.py`, `test_symmetric_knife*.py`,
`test_symmetric_extrude.py`, `test_knife_kept_calls.py`, `test_symmetric_split.py`, …; `git diff --stat
eaf43a3..f65d223`). `tests/test_extrude_tool.py` moved to `tests/_archive/` (`07d541c`), so the handoff's
`--ignore` is now a no-op; `pytest.ini` excludes `_archive`. **Re-run at `eaf43a3` itself** (a `git archive`
export, same container): `pytest tests --ignore=tests/test_extrude_tool.py` → **2028 passed, 6 skipped**;
`pytest experiments/symmetry_lab/tests` → **433 passed, 4 skipped** — the handoff's numbers, reproduced.

### 0.2 Delta `eaf43a3` → `f65d223`, checked for the handoff's stop condition

- **Core unchanged.** `git diff eaf43a3..f65d223 -- src/core` is empty; so is `git diff 02a08c3..f65d223 --
  src/core src/mirai/interaction/tools` (`02a08c3` = the S1 baseline). FINDINGS §4.1 (E10 table) and every
  Core observation in FINDINGS still describe the current code.
- **Transform tools unchanged** (`src/mirai/interaction/tools/`, same diff).
- **`Application`'s Move/Rotate/Scale path unchanged in behaviour.** The only changes in `key_press`,
  `key_release`, `_transform_arm`, `_transform_step` and `_cancel` are additive `EXTRUDE` branches placed
  before the unchanged Move/Rotate/Scale branches; `_transform_end` only also resets the Extrude state
  (function-by-function AST diff of `src/mirai/application.py` at both commits). Extrude joined the hold-key family:
  `_TRANSFORM_COMMANDS` (`application.py:110-115`), `interaction_owner` = `"transform"` while T is held
  (`:1403-1414`), constraint keys ignored during Extrude (`:1450-1454`).
- **New binding `T` → Extrude** (`bindings.py:129`). Relevant for Q5 only.
- **Viewport:** new Knife symmetry tool layers (`overlay.py:74-96`, draw order `viewport.py:83-96`);
  `add_overlay` and `on_vertices_moved` unchanged.

No contradiction with FINDINGS or the handoff. The recommendation was therefore written.

### 0.3 Taken as given (not reopened)

- **Artist (Manu, 2026-10-08):** Soft Selection in parallel with Symmetry, independent of it for now;
  validation in the Production viewport, not the Playground; no Symmetry integration design.
- **E1** Soft Selection is not a selection mode; influence never enters `Selection`; one gesture = one History
  step; AD-016 hold-key W/E/R.
- **E2** S1 semantics are the baseline candidate (FINDINGS §4): weighted Move/Rotate, Scale absolute for
  `w < 1`, pivot from the primary selection, influence transient at `begin()`.
- **E3** Soft + Symmetry on the app path: refused visibly (fail-closed). This AD names the contact points
  (§8) and nothing more.
- *(Assumption, handoff, not confirmed by Manu)* S2 is an Artist comparison test, so metric, curve and a few
  radius steps must be switchable in the window.

### 0.4 Scratch probes (container, not committed)

The handoff allows no file but this AD, one index line and the FINDINGS pointers. Two probes were run in the
session scratchpad instead and are reproduced in shape in Appendix A and B:

- **P-D** — Q2 alternative D (soft ops on the documented extension points of `VertexTransformOperation`)
  against the S1 ops and the Core ops. Result in §3.2.
- **P-V** — the viewport share of a soft drag, approximated by a plain W drag of exactly the influenced
  vertex set through `Application` + `Viewport` (TraceStore). Result in §7.2.

---

## 1. Existing facts the questions rest on

**The transform path (W/E/R).**

- F1 [Code] Arm: the target is fixed at the key press — the resolved selection, else the hovered element's
  vertices (`application.py:1507-1543`, `resolve_selection_vertices` at `:1518`). Begin at the first motion:
  `_transform_space = self._axis_constraint` is read once (`:1581`) and the tool gets
  `{"scene", "camera", "vertex_ids": set(self._transform_target), "space"}` (`:1584-1590`). Every step then
  calls `on_vertices_moved(self._active_transform_vertex_ids())` (`:1603`), which reads `MoveTool.moves` or
  `TransformTool.vertex_ids` (`:1606-1612`); `_cancel` notifies the same set (`:1759-1762`).
- F2 [Code] Sticky state precedent: `_axis_constraint` survives commit, cancel and re-arm and is read at every
  `begin()` (`application.py:418-422`); a constraint key during a running gesture changes only the state, the
  new value applies from the next gesture (`_constrain`, `:1548-1556`).
- F3 [Code] A tool start refusal is already a visible path: `SeamConstraintError` from `begin` ends the
  transform with a status line, no history, unchanged mesh (`application.py:1591-1598`).
- F4 [Code] Tools are re-instantiated on every activation (`tool = tool_class()`,
  `tool_manager.py:74-76`), so no state survives in a tool between gestures.
- F5 [Code] `TransformTool._on_begin` hands the Core op a `_VertexSelectionView(vertex_ids)` and
  `params = {"pivot": ...}` (+ `"symmetry"` when a definition is set) (`tools/transform.py:348-379`);
  `MoveTool` likewise (`tools/move.py:190-221`). The Move anchor for the screen→world mapping is
  `min(vertex_ids)` of the *selected* set, taken before partners are added (`tools/move.py:125`).
- F6 [Code] **Rotation axis is constant per gesture on the app path:** `RotateTool` fixes `self._axis` in
  `begin` (`tools/rotate.py:101-116`) and passes it unchanged on every update (`:133`). **Scale basis is
  constant per gesture:** `ScaleTool` fixes `_tangent_basis` in `begin` (`tools/scale.py:119`) and passes it,
  or `None`, on every update (`tools/scale.py:175`, `:179`). So FINDINGS L4 (path dependence under a changing
  axis) and L5 (one basis per gesture) never arise from the Production tools.

**The Core seam.**

- F7 [Code] `VertexTransformOperation._on_update` is one per-vertex loop for Move/Rotate/Scale: it calls
  `_transform_position(pos, vertex_id=vid, **kwargs)` and then applies the placeholder blend
  `pos + w·(new − pos)` only if `self._weights[vid] != 1.0` (`transform.py:261-270`). `_on_begin` sets every
  weight to `1.0` (`:227`), and nothing in the Core sets them otherwise. FINDINGS §3.4/B1: the blend is not
  path independent.
- F8 [Code] Documented extension points: `Operation` subclasses implement the four `_on_*` hooks
  (`operation.py:82-85`, `:128-145`); `VertexTransformOperation` subclasses implement only
  `_transform_position()` (`transform.py:214-218`, `:289-295`); `MoveOperation` itself extends `_on_begin`
  with a super-call (`core/operations/move.py:91-101`). Public: the `pivot` and `vertex_ids` properties
  (`transform.py:252-259`), `rotate_around_axis` (`:98-118`), `VertexTransformCommand` (`:187-208`, exported
  in `core.__all__`). `ScaleOperation._apply` is private (`:418-435`).
- F9 [Code] The update contract is incremental; an operation that needs absolute evaluation "muss das
  explizit und sichtbar abweichend dokumentieren" (`operation.py:15-25`).
- F10 [Code] No `src/mirai` module reads or writes a Core private member, and none subclasses a Core
  `Operation` (grep over `src/mirai` for `_weights`, `_start_positions`, `_transform_position`, `._apply(`,
  `class …(…Operation)`). `src/mirai` does import module-public names from `core.operations.transform`
  (`SeamConstraintError` `application.py:44`, `rotation_keeps_plane` `tools/rotate.py:38`,
  `scale_keeps_plane` in `tools/scale.py`, `pivot_on_plane` `tools/selection_helpers.py:12`).
- F11 [Code] CORE_V1_FREEZE §4 lists "Soft Selection / Influence-System" among the systems not pulled into
  Core V1; §7 is the rule for exceptions. V1_CORE §6 asks for a replaceable falloff strategy; FINDINGS
  `influence.py` provides it as two registries.

**The viewport.**

- F12 [Code] `Viewport.add_overlay(o)`: `o.sync(mesh, selection)` runs in `sync()` whenever selection/hover,
  vertex positions or topology were reported, or when `o.dirty` is set; `o.draw(camera_uniforms)` runs after
  the tool lines and before the point overlay (`viewport.py:52-59`, `:162-166`, `:244-257`, `:319-320`).
  `GLPointOverlay` takes its layers and styles as class attributes so a host can subclass it
  (`gl_point_overlay.py:125-134`); points ignore depth (`:211`). The Symmetry Lab uses exactly this
  (WP-SYM-LAB-03 H1).
- F13 [Code] `set_tool_overlay(points, segments)` replaces **all** tool layers at once (`viewport.py:170-183`);
  the Knife is its writer.
- F14 [Code] The per-vertex face tint is gone (AD-018 §7 E18, Artist **REJECT** 2026-09-26: "reads like
  vertex paint"); the `highlight_flags` attribute stays in the `RenderMesh` layout (`render_mesh.py:74`) but
  the fragment shader no longer reads it (`gl_render_store.py:63-93`), so Manu's driver optimises it out
  (hotfix, `gl_render_store.py:213-219`). Its removal is a recorded follow-up (AD-018 §7).
- F15 [Code] `RenderMesh._sync_geometry` per frame with moved vertices: 1-ring face and vertex normals,
  `recompute_bounds` over **all** vertices, partial uploads per moved vertex (`render_mesh.py:277-314`,
  `derived.py:305-307`). With edges shown, `edge_segments(mesh)` is rebuilt in full per dirty frame
  (`viewport.py:275-281`, AD-018 §7 extension B5a).

**Input.**

- F16 [Code] Occupied inputs (`build_default_bindings`, `bindings.py:107-182`): GLOBAL 1/2/3, Ctrl+Z, Ctrl+Y,
  Esc, W/E/R, T, X/Y/Z, Shift+X/Y/Z, Alt+A, C, Delete, Backspace, Ctrl+Backspace, D, Shift+D; mouse LMB
  (plain/Shift/Ctrl/Alt click), Alt+LMB drag, Alt+Shift+LMB drag, wheel up/down = Zoom. KNIFE context: Enter,
  E, RMB click, Ctrl+Shift+Z; plus plain V, hard-coded (not a binding) while a symmetric Knife session runs
  (`KNIFE_MIRROR_VARIANT_KEY`, `application.py:250`, `:1022-1024`; AD-SYM-03 slice 6c, `PROVISIONAL`).
  TOPOLOGY context: K, L, R. Symmetry Lab context: Shift+S, M, Shift+B
  (`experiments/symmetry_lab/lab_bindings.py:46-62`), with a start-up assert that they resolve to `None` in
  GLOBAL and KNIFE (AD-013 H2-R1). Artist Input Truth reserves, beyond these, F (frame), S (split),
  Shift+C, Shift+L, Shift+R, I, G, H (`tools/Input_Mapping_Tool/artist_input_truth.json`); it has **no**
  Soft Selection entry. Q is unbound by Artist decision (AD-013 addendum 2026-09-26, `:391`).
- F17 [Code] The window adapter translates only A–Z, 0–9, Tab, Esc, Space, arrows, Enter, Backspace, Delete
  (`pyglet_input.py:54-69`); `on_mouse_scroll` carries no modifiers (`main.py:207-211`,
  `pyglet_input.py:142-153`).

**The Symmetry Lab (runs the app path).**

- F18 [Code] Under BLOCK (the Lab default) the gate is fail-closed: every command outside `NON_OPERATION`
  and the declarations is refused visibly (`lab_app.py:125`, `:132-170`, `:293-…`; AD-013 G-2 amendment,
  which lists `NON_OPERATION` "exactly", `:933`). The Lab's fail-closed tests parametrise over every
  constant in `mirai.interaction.commands` (`test_app_lab_fail_closed.py:82-85`, `:184-218`), so a new
  command constant is covered automatically.

---

## 2. Q1 — Host for S2

### 2.1 Alternatives

| | Alternative | What `src/main.py` shows | Effect on the Symmetry Lab | Governance cost |
|---|---|---|---|---|
| **A** | **In the app as a `PROVISIONAL` capability, off by default, one toggle key** (WP-06 / AD-013 pattern) | Nothing new at start. O → status line, band points around the selection; W/E/R then move the falloff region. Soft off = today's code path | The Lab inherits the keys and the capability (same `Application`). Soft + symmetry is refused by `Application` at arm (§8). One Lab-side change: the soft setting commands join `NON_OPERATION` (they start no interaction and change no mesh, like X/Y/Z), else O is refused under BLOCK and soft cannot be switched off while symmetry is on. The Lab's fail-closed tests derive their expectations from `NON_OPERATION` and the command constants, so they need no edit (F18; read, not run) | No Core change (with Q2-D). AD-013: the Artist decision of 2026-10-08 is the explicit decision that puts an unvalidated capability on the Production path; capability, keys and look stay `PROVISIONAL` (I7, I8). A dated note in AD-013's G-2 amendment for the `NON_OPERATION` addition. No new gate writer (H2-R6 untouched). S2 docs: this AD, `src/main.py` docstring, ROADMAP §7 intake |
| B | **A second app-path Lab** (`experiments/soft_selection/…`, like the Symmetry Lab) | Unchanged | Unchanged | W/E/R must use soft ops, but nothing in `Application` lets a host influence how a transform begins. H2-R4 forbids the Lab `dispatch_command`, underscore members, `ToolManager` and transform arming; H2's core rule is "`Application` calls no experiment code" (`AD-013:500`). So B needs a new `Application` hook (a data hook "influence for the next gesture", or an operation factory) plus a new AD-013 addendum and review (H2-R6: a second host needs its own review). The weighted ops would still have to live in `src` (Application cannot construct experiment classes), and a host-computed influence cannot follow the hover target `Application` resolves at arm (F1) |
| C1 | App capability (as A), but **no default bindings**; enabled by a start option of `src/main.py` (or a `keymap.json` user layer) | Unchanged unless started with the option | Unchanged (no keys bound there) | As A, minus the `NON_OPERATION` note; plus a second start mode of a deliberately thin entry point (`main.py:72-80`) and a hidden capability the Artist must start specially |
| C2 | Playground | — | — | Excluded by the Artist decision of 2026-10-08 (validation in the Production viewport) |

### 2.2 Rejected alternatives

- **B is not used because** it needs a new `Application` hook and a new AD-013 H2 review to reach the same
  W/E/R gesture A uses directly, and it still puts the weighted ops into `src`.
- **C1 is not used because** "off by default" already keeps the default app unchanged; a start option adds a
  second way to run `src/main.py` for no further protection, and the Symmetry Lab's only cost under A is one
  constant.
- **C2 is not used because** the Artist decided validation in the Production viewport.

### 2.3 What A means for "experiment first" (AD-013 § Default Lifecycle)

Soft Selection is a new, unvalidated capability, so AD-013's default would be the Playground or an experiment.
S1 *was* the experiment (headless); the Artist decided on 2026-10-08 that S2 validates in the Production
viewport. That is the explicit decision AD-013 asks for. It promotes nothing: the capability stays
`PROVISIONAL` in `src/mirai`, the keys are an engineering proposal (not Artist Input Truth, I8), and promotion
(capability and UX separately, I7) is a later decision after the S2 verdict (§12).

---

## 3. Q2 — Core seam

### 3.1 Alternatives

- **A — Targeted Core change (AD-014 style).** `VertexTransformOperation` takes `params["influence"]`;
  the placeholder blend (F7) is replaced by weighted parameters per subclass (`w·Δ`, `w·θ`, Scale absolute
  for `w < 1` with the factor accumulated since `begin()`).
- **B — A small public Core hook** that weighted ops outside the Core use (e.g. a documented per-vertex
  step hook plus public access to the start snapshot and the accumulated update state).
- **C — The S1 ops as they are, moved to `src/mirai`** (subclasses of `MoveOperation`/`RotateOperation`/
  `ScaleOperation` using the Core privates of FINDINGS §4.1).
- **D — new: soft ops in `src/mirai` on the documented extension points only.** Subclasses of
  `VertexTransformOperation` (module-public, F10) that implement `_transform_position(pos, vertex_id, …)`,
  extend `_on_begin` with a super-call (read and validate `params["influence"]`, keep an own weight map and
  an own start snapshot), and — Scale only — extend `_on_update` with a super-call (accumulate the total
  factor, enforce one basis). Rotate uses the public `rotate_around_axis(pos, self.pivot, axis, w·θ)`;
  Move uses the same tuple sum as `MoveOperation` (`core/operations/move.py:110`); Scale copies the arithmetic
  of the private `ScaleOperation._apply` (`transform.py:418-435`). Snapshot, commit, cancel and the History
  command remain the Core's (`VertexTransformCommand`). The base never blends, because its own `_weights`
  stay `1.0` (F7).

### 3.2 Probe P-D [Probe]

Head mesh, seed = one vertex plus its one-ring (5 seeds), pivot = seed centroid, radius 0 and 1.0, both
metrics, 60 updates per gesture (random deltas; random angles about a fixed oblique axis; random per-axis
factors in a tilted orthonormal basis):

| Check | Result |
|---|---|
| D vs S1 ops (`weighted_ops.py`), positions after 60 updates and the History command's start/end maps, all 12 cases (3 ops × 2 metrics × 2 radii) | **bitwise identical** |
| D vs Core `MoveOperation`/`RotateOperation`/`ScaleOperation` at radius 0, same explicit pivot | **bitwise identical** (3 ops × 2 metrics) |
| D path independence, 1 step vs 60 steps (radius 1.0, euclidean, smooth) | Rotate 4.9e-15, Scale 3.1e-15 (float rounding, as FINDINGS L1) |
| Core private members referenced by the D classes (`_weights`, `_start_positions`, `_vertex_ids`, `_pivot`, `_mesh`, `_apply`) | **none** |

### 3.3 Assessment

| | Freeze impact | Core privates used from `src` | L3 radius-0 bit identity | L6 identity gestures | L5 basis | L4 axis | Cost for S2 | Promotion path |
|---|---|---|---|---|---|---|---|---|
| A | CORE_V1_FREEZE §7.1 exception in the loop every Move/Rotate/Scale gesture runs through, symmetric ones included (F7); needs the AD-014 argument "`w == 1` path byte-identical"; the absolute Scale evaluation is a visible deviation from the incremental contract (F9) | none | holds if the `w == 1` path keeps today's arithmetic (as S1 showed) | unchanged unless `_on_commit` changes for all transforms | the Core interface must state "one basis per gesture" when weights are given (today a new basis per update is accepted, FINDINGS L5) | unchanged | **high**: a Core change, its review and Core contract tests before the Artist has seen the semantics (scale formula, curve) — which S2 exists to decide | is the promotion |
| B | §7.1 exception (smaller than A) | the hook must expose start snapshot and accumulated update state — the soft API designed inside the Core | holds | unchanged | stated in the hook's docs | unchanged | medium-high | the hook is designed before its semantics are known and then again at promotion |
| C | none | **nine rows** (FINDINGS §4.1): `_on_begin` with a substitute context, wholesale `_on_update` override that bypasses the seam check, `_weights`, `_mesh`, `_vertex_ids`, `_pivot`, `_start_positions`, `_transform_position`, `_apply` — the first private-member coupling in `src/mirai` (F10) | holds (FINDINGS L3) | inherits the Core | soft Scale enforces it; the app path never changes it (F6) | the app path never changes it (F6) | lowest (move S1) | FINDINGS §4.1: E10 must be resolved before any promotion — C carries it into `src` unresolved |
| **D** | **none** | **none**; documented hooks (F8), public `pivot`, `rotate_around_axis`, `VertexTransformCommand`; one copied formula (Scale), pinned by a radius-0 identity test against `ScaleOperation` | **holds** (P-D, bitwise) | inherits the Core's `_on_commit` (same as plain transforms) | soft Scale enforces it; the app path never changes it (F6) | the app path never changes it (F6) | low (same class names, params and update kwargs as S1; the S1 suite ports with one helper change: `soft_context` hands the op a view of the influenced set, as most S1 tests already do, `test_weighted_ops.py:61-63`) | open, separate AD after the S2 verdict: keep D in `src/mirai`, or fold the weighting into the Core (A) |

What D still depends on, stated so it is not hidden:
- the base keeps `_weights` at `1.0` (F7). If the Core ever fills them (that is A), D must go in the same
  change — which is exactly the promotion decision;
- the base loop passes `vertex_id=` to `_transform_position` — a documented Core contract since AD-SYM-02
  (CORE_V1_FREEZE §7.1, entry 2026-09-24);
- the copy of `ScaleOperation._apply`; the radius-0 test fails loudly if the Core formula changes
  (AD-014 changed it once).

### 3.4 Rejected alternatives

- **A is not used for S2 because** it changes the frozen loop every Move/Rotate/Scale gesture runs through
  for a capability the Artist has not yet seen; CORE_V1_FREEZE §1/§7 asks for a concrete requirement, and the
  S2 verdict is what turns "soft selection exists" into one. It stays the leading candidate for promotion.
- **B is not used because** it is a Core change too, and its shape depends on exactly the semantics S2 is
  meant to settle (absolute Scale, basis contract), so it would be designed twice.
- **C is not used because** it makes `src/mirai` the first Production code coupled to Core private members
  (the nine rows of FINDINGS §4.1) and to a seam-check bypass, which FINDINGS says must be resolved before
  promotion; D resolves it at about the same cost with bitwise-equal results.

### 3.5 FINDINGS §5 items touched here

- §5.5 (identity gestures): D behaves as the Core (History entry for a visually empty Rotate/Scale, L6). S2
  keeps that; the question stays open for promotion.
- §5.6 (basis contract): on the app path one basis per gesture is already the case (F6); D enforces it in
  the soft Scale. A Core interface statement is only needed under A.
- §5.7 (changing axis): no Production tool changes the axis mid-gesture (F6). Whether the contract should
  *say* "constant axis" is a question for A only.
- §5.10 (radius-0 identity with the tool's pivot): S2 keeps L3 as an op-level test with the pivot handed to
  both ops explicitly (as S1 and P-D do). On the app path the plain tools use the Core's default pivot
  (centroid in set iteration order), the soft tools the seed centroid (E7); a last-bit difference there is
  invisible and is not an S2 requirement.

---

## 4. Q3 — Influence channel and state

### 4.1 Who computes the influence

**Proposal: the tool, in `begin()`.** `Application` adds the sticky soft settings to the begin payload
(`"soft": settings` or `None`, next to `"space"`, F1). `TransformTool._on_begin` / `MoveTool._on_begin`,
when `soft` is set:
1. take the seeds = `vertex_ids` (= `_transform_target`: the selection, else the hovered element — the same
   vertices the plain tool would move, S1 E3);
2. compute `compute_influence(mesh, seeds, radius, metric, curve)` from the current (= start) positions (E2);
3. for Rotate/Scale pass `pivot = primary_pivot(seeds)` (E7);
4. build the context with `_VertexSelectionView(influence keys)` and `params = {"influence": …, "pivot": …}`
   and create the soft op (Q2-D);
5. report the influenced set as the affected set (`moves` / `vertex_ids`), so `on_vertices_moved` and
   `_cancel` cover every moved vertex (F1). The Move anchor stays a seed (`min(seeds)`, F5), so the
   screen→world mapping is the plain Move's.

Not used: **`Application` computes the influence and passes it in** — it would put falloff knowledge into the
orchestrator, and the tool has to branch for the soft op anyway. **The operation computes it** — the influence
system is outside the Core by CORE_V1_FREEZE §4 and V1_CORE §6 (replaceable strategy), and under D the op
lives in `src/mirai` but should stay a pure "weights in, positions out" unit, as S1 tested it.

### 4.2 Channel

**`params["influence"]`** (`{VertexId: w}`, `0 < w ≤ 1`), like `pivot` and `symmetry` (AD-SYM-02 §2.2: the
generic `params` channel, no new field on `OperationContext`). The op refuses a missing map, weights outside
`(0, 1]`, a vertex set that differs from the map's keys, and `params["symmetry"]` (§8), all at `begin()` before
anything moves (S1 L10, extended by the key-set check that D needs).

- **A typed field on `OperationContext` is not used because** it is a Core change (`operation.py:56-73`) with
  no benefit over the existing channel.
- **Influence in `Selection` is not used because** E1 forbids it.

### 4.3 Where the settings live

**`Application`, as one small sticky value** (working name `SoftSettings`: enabled, radius step, metric,
curve; frozen, replaced as a whole), with the semantics of the axis constraint (F2): survives commit, cancel,
re-arm and Undo; read once per gesture at `begin()`; a change during a running gesture changes the state and
posts a status line, and applies from the next gesture. *(Engineering proposal; whether a mode switch should
reset it is left to the Artist.)*

- **Tools are not used because** they are re-instantiated per activation (F4).
- **`DisplayState` is not used because** it is view state; soft settings change what a gesture does.
- **The Viewport is not used because** it is passive (Core → Viewport only).

**Radius unit for the test.** S2 needs some unit to run. Proposal: the S1 probe's unit, a fraction of the
mesh's bounding radius (`probe_cost.py:142-148`), with a short step list such as the probe's 5 / 15 / 30 %,
because reference-PC numbers exist for exactly those (FINDINGS §2.2). This is a **test setting, not the
default of FINDINGS §5.4**, which stays an Artist question the S2 test is meant to inform. Note:
`mesh_center_and_radius` scans every vertex with `math.dist` (`mesh_geometry.py:44-46`), so it should run
once per mesh state (e.g. on toggle and after topology changes), not per move; its cost on the reference PC is
unmeasured (*(Reading)*: by FINDINGS R6, ~928 × 3.2 µs ≈ 3 ms on the body mesh).

### 4.4 Is "transient at `begin()`" (E2) enough once the viewport shows weights? (FINDINGS §5.2)

**Yes, for S2.** The preview (§5) is a second, display-only evaluation of the same pure function; it is never
fed into the op. Before a gesture nothing moves between the preview and `begin()` (positions change only
through gestures, Undo/Redo, topology commands and a host's `apply_mesh_change`, each of which notifies the
Viewport and so triggers a recompute), so both agree; an S2
test can pin `preview == influence at begin`. During a gesture the overlay shows the op's weights (fixed since
`begin()`) at the live positions and never recomputes.

---

## 5. Q4 — Minimal visualization

### 5.1 Alternatives

| | Alternative | `src/viewport` change | Assessment |
|---|---|---|---|
| **a** | **Banded point layers**: a `GLPointOverlay` subclass with a few band layers (e.g. four bands over `0 < w < 1`, warm → cold), attached with `Viewport.add_overlay` (F12) | **none** | The H1 precedent (Symmetry Lab markers). Data is headless: weights → band → `mesh.vertex_position`; positions follow the drag because `on_vertices_moved` already makes `sync` call the overlay. Seeds keep the existing selection look. Cost per move: one `set_points` per band over ≤ 112 points (*(Reading)*, measured by the S2 probe, §7) |
| b | New tool layers through `set_tool_overlay` | `overlay.py` / `gl_point_overlay.py` layer additions | `set_tool_overlay` replaces every tool layer at once and the Knife writes it (F13): two writers would clear each other's layers; tool layers also mean "during a modal session", while the soft preview shows when idle |
| c | Per-vertex colour attribute on the mesh (re-use `highlight_flags` or a new attribute + a fragment-shader mix) | `RenderMesh` layout, `GLRenderStore` shader, a new Viewport setter | This is the face tint the Artist rejected for the selection (F14), on a pipeline whose removal is already planned; the driver currently drops the attribute. Highest cost and against the direction of an Artist verdict |
| d | Edge lines coloured by band (`FlatColorLayers` subclass) | none | Visible only while edges are shown; an edge between two bands has no single colour |

**Preview scope** *(engineering proposal)*: from the selection only, recomputed when the selection, the mode,
the settings or the mesh change; no preview from the hover target (hover changes are the most frequent event,
and on the reference PC a hover change on the body mesh already costs ~9.5 ms in the Symmetry Lab measurement,
WP-SYM-LAB-03 plan A3). For a hover-armed gesture the bands appear with the first motion.

**Wiring:** the overlay class lives with the soft code in `src/mirai`; `Application.init_scene` gets one more
pass-through type parameter (`soft_overlay_type=None`, the E17 pattern of `point_overlay_type`,
`application.py:493-555`), and `src/main.py` passes the GL class in `GL_TYPES` (`main.py:118-124`). The
Viewport stays unaware of soft selection.

### 5.2 Rejected alternatives

- **b is not used because** the tool layers have one writer (the Knife) and are replaced as a whole.
- **c is not used because** it re-introduces the rejected face tint on a pipeline that is to be removed, and
  needs a `src/viewport` layout and shader change. Whether a tint reads differently for *influence* than for
  selection is a question for Manu in S2c, not an engineering default.
- **d is not used because** it depends on the edge display mode and is ambiguous between bands.

Band count, colours and point size are `PROVISIONAL` look values for the S2 handoff. Points ignore depth
(F12), so influenced vertices on the far side stay visible through the mesh, as selected points do today —
one thing to watch in S2c at large radii.

---

## 6. Q5 — Minimal S2 controls

### 6.1 Proposal (`PROVISIONAL`, engineering, not Artist Input Truth)

| Function | Key | Conflict check (F16, F17) |
|---|---|---|
| Soft Selection on / off | **O** | Free in GLOBAL, KNIFE, TOPOLOGY, Symmetry Lab; no Artist Truth entry uses O. In the adapter map. Precedent *(recalled, not verified here)*: Blender's proportional editing toggle |
| Radius one step larger / smaller | **Up / Down** (arrows) | Free everywhere; in the adapter map (`"up"`/`"down"`); layout-independent. Clamped at the ends, no wrap |
| Curve smooth ↔ linear | **Shift+O** | Free everywhere. *(Recalled, not verified)*: Blender's Shift+O cycles the falloff type |
| Metric euclidean ↔ geodesic | **Ctrl+O** | Free everywhere. Ctrl+O is the common "Open" convention; Artist Truth `application.load` is unbound today |
| *(optional, only if Manu wants the scale formula switchable in S2)* linear ↔ power | Ctrl+Shift+O | Free everywhere |

Behaviour: sticky like X/Y/Z (F2); allowed while W/E/R/T is held (state only, applies from the next gesture);
inside a Knife session the keys go to the Knife context first and do nothing (`application.py:1443-1444`).
Each press posts one status line with the full state (e.g. `Soft: on · 15 % (0.51) · euclidean · smooth`,
`PROVISIONAL` until a HUD exists). Four new command constants in `mirai.interaction.commands`; four defaults
in `build_default_bindings()`, re-bindable through `keymap.json` (I4/I5).

Symmetry Lab check: none of the proposed inputs is Shift+S, M or Shift+B, so the Lab's start-up assert and
T-R1a (GLOBAL/KNIFE equal `build_default_bindings()` after Lab start-up) hold unchanged.

### 6.2 Rejected alternatives

- **B (Maya's soft-select key) is not used because** Shift+B is the Symmetry Lab's E5 key; exact modifier
  matching keeps them apart, but one letter would carry two unrelated meanings in the Lab.
- **The mouse wheel, plain or modified, is not used because** the wheel is Zoom (`bindings.py:171-172`) and
  `on_mouse_scroll` carries no modifiers (F17); a modified wheel needs modifier tracking in the window, like
  the Knife's Shift tracking (`main.py:146-156`).
- **`[`/`]` and `+`/`-` are not used because** the adapter does not translate them (F17), so S2 would change
  `pyglet_input`, and their position depends on the keyboard layout.
- **Digits 4–9 are not used because** they sit next to 1/2/3, which switch the mode and clear the selection
  (`application.py:608-621`), and V1_SPEC §2 reserves 4 for Object mode.
- **Hold-key + drag for the radius (Maya-style) is not used because** it is a new gesture; AD-013 A3 is open
  beyond Transform.
- **Q is not used because** the Artist unbound it deliberately (AD-013 addendum 2026-09-26).
- **V is not used because** it is the symmetric Knife's hard-coded mirror-variant key inside a session (F16);
  outside a session it would be free, but one letter would again carry two meanings.

---

## 7. Q6 — Viewport cost of a soft drag on the reference PC (FINDINGS N5)

### 7.1 What is known

- Operation share per update on the reference PC ≤ 0.67 ms; influence once per gesture ≤ 2.2 ms
  (FINDINGS R1, R10, §2.2).
- Symmetry Lab, reference PC, a symmetric W drag with **12** moved vertices: transform step + Lab overlays
  p95 0.40 / 0.86 ms, the app's own remaining `viewport.sync` p95 1.04 / 1.44 ms (head / body;
  WP-SYM-LAB-03 plan A3). That bar (p95 ≤ 8 ms per move) excluded the app's own sync.

### 7.2 Probe P-V [Probe] — container, **not the reference PC**

A plain W drag of exactly the influenced vertex set (same seeds as the S1 probe: front-most vertex + one-ring;
the influenced counts match FINDINGS §2 exactly), 200 moves through `Application.pointer_motion`, then
`viewport.sync()` per move (TraceStore: CPU side only, no upload, no draw). The weighted op is not in it (its
share is FINDINGS §2), and neither is a band overlay. Whole move (step + sync), ms:

| Asset | radius | metric | moved | p95, edges hidden | p95, edges shown |
|---|---|---|---|---|---|
| head (326 V) | 5 % | euclidean / geodesic | 9 / 9 | 0.42 / 0.35 | 0.65 / 1.01 |
| head | 15 % | euclidean / geodesic | 36 / 30 | 0.73 / 0.70 | 1.46 / 1.28 |
| head | 30 % | euclidean / geodesic | 68 / 61 | 1.17 / 1.02 | 1.74 / 1.91 |
| body (928 V) | 5 % | euclidean / geodesic | 18 / 10 | 0.79 / 0.97 | 1.36 / 1.33 |
| body | 15 % | euclidean / geodesic | 76 / 28 | 2.06 / 0.98 | 2.14 / 2.94 |
| body | 30 % | euclidean / geodesic | 112 / 107 | 1.57 / 2.53 | 2.84 / 2.30 |

Run-to-run spread in the container is up to ~2× per cell (FINDINGS N3); orders of magnitude are what counts.
A `cProfile` run (body, 30 %, euclidean) puts almost all of the per-move time into `viewport.sync`:
`RenderMesh._sync_geometry` (1-ring face/vertex normals, the per-vertex partial updates and the O(V)
`recompute_bounds`, F15) and, with edges shown, an equal share for the full `edge_segments` rebuild; the
transform step is ≈ 10 %.

*(Reading, not measured)*: with the 3–5× container → reference-PC factor seen for the update columns
(FINDINGS R1) and ≈ 5× in WP-SYM-LAB-03 A3, the worst rows land around **8–15 ms** per move on the reference
PC — at or above the 8 ms bar, mostly in **existing** per-move viewport work that any W drag of ~100 vertices
pays today. Soft Selection makes large moved sets the normal case.

### 7.3 Proposed measurement (S2, reusing the Symmetry Lab probe approach)

A headless probe in `experiments/soft_selection/` (reads `src` only, like `probe_cost.py`), built like
`experiments/symmetry_lab/probe_drag_cost.py`: `Application` + `init_scene` (TraceStore) + the soft band
overlay attached as in the window; everything through the public entry points (`pointer_*` clicks for the
selection, `key_press` for O / radius / metric / curve and W/E/R, `pointer_motion` × N, `key_release`),
`viewport.sync()` after every move. Output to paste into the chat, per asset × radius step × metric × W/E/R:

- **per move** p50 / p95 / max: whole move, transform step, `viewport.sync` (incl. the band overlay);
- **once per gesture:** the first move (`begin` incl. influence) and the commit frame;
- **preview:** a selection change and a settings change with soft on (influence + bands);
- edges hidden and shown.

**Bar** *(engineering proposal)*: whole move (step + sync) p95 ≤ 8 ms on the reference PC — stricter than
A3, because soft enlarges the app's own share. Gesture start, commit frame and preview are reported, not
gated. **Gate:** Manu runs it on the reference PC before the practical test (S2b → S2c, §10). If the bar is
missed, the fix is a viewport question (e.g. bounds or edge segments per move), decided separately, not a
reason to change the soft semantics.

Not measured, as in A3: GPU upload and draw. If S2c feels slow although the probe passes, a window-side frame
timer is the follow-up.

- **Measuring only in the window is not used because** the reference PC is reachable only through Manu, and a
  headless one-command probe gives comparable numbers across machines (the A3 precedent).

---

## 8. E3 — Soft + Symmetry contact points (named, not designed)

1. **`Application`, at arm (primary).** W/E/R with soft on while `mesh.symmetry_definition is not None` →
   refused visibly at the key press (status line, nothing armed, no history), in MARK and BLOCK alike.
   `src/main.py` never sets a definition (T-G3b), so Production never reaches it; the Symmetry Lab does.
2. **The soft op (backstop).** `params["symmetry"]` present → `ValueError` at `begin()` before anything
   moves, as S1 E9; the soft ops declare no symmetry support (`supports_symmetry` stays `False`, the
   `Operation` default, `operation.py:88`). Under Q2-D they do not inherit the seam machinery of
   `_PivotTransformOperation` (`transform.py:298-366`), so nothing is bypassed.
3. **The shared Core loop.** Symmetry (`vertex_id` → category in `_transform_position`) and the soft
   placeholder (`_weights`) meet in the same per-vertex loop (F7; AD-SYM-02 §1 "genau eine Stelle"). Under
   Q2-D soft does not use the placeholder, so the two do not touch in S2. Under Q2-A they would share the loop,
   and the combination would have to be refused or designed there.
4. **The Symmetry Lab gate.** The soft setting commands join `NON_OPERATION` (§2.1). Not adding them would
   refuse O under BLOCK (fail-closed, F18), so soft could not be switched off while symmetry is on.

Mirrored influence, seam vertices with `w < 1` and every other part of a symmetric soft gesture
(FINDINGS §5.8) are out of scope.

---

## 9. Recommendation

| Q | Recommendation | Main reasons |
|---|---|---|
| Q1 | **A** — in the app, `PROVISIONAL`, off by default, O toggles | The Artist decided validation in the Production viewport; no new `Application` hook, no AD-013 H2 review, no Core change; soft off is today's code path; the Symmetry Lab needs one constant |
| Q2 | **D for S2** — soft ops in `src/mirai` on the documented extension points; **no Core change**. A (Core) vs. keeping D is decided in its own AD after the S2 verdict | Bitwise equal to S1 and, at radius 0, to the Core (P-D); no private Core member in `src` (resolves FINDINGS E10 instead of carrying it); the frozen loop stays untouched until the Artist has judged the semantics |
| Q3 | Tool computes the influence at `begin()` from the seeds; `params["influence"]`; sticky `SoftSettings` in `Application` (axis-constraint semantics) | Mirrors existing patterns (`space`, `pivot`, `symmetry`, `_axis_constraint`); E1 and E2 hold unchanged |
| Q4 | **a** — banded points via `add_overlay`, preview from the selection, op weights during the gesture | No `src/viewport` change, the H1 precedent, no return of the rejected tint |
| Q5 | O, Up/Down, Shift+O, Ctrl+O (+ optional Ctrl+Shift+O) | All free in every context incl. the Lab and the Artist Truth; in the adapter map; one letter for everything soft |
| Q6 | The app-path probe of §7.3, run on the reference PC before the practical test | P-V suggests the bar may be missed at 30 % on the body mesh, mostly in existing viewport work |

---

## 10. Sketch of the S2 slice cut (not a handoff)

- **S2a — capability on the app path, headless.** `src/mirai/soft_selection/` (influence from S1 incl. the
  `math.sqrt` form; the three soft ops per Q2-D); tool wiring (§4.1); `SoftSettings` in `Application`, the four
  commands and bindings, status lines, the arm-time refusal (§8.1); Symmetry Lab `NON_OPERATION` + dated
  AD-013 note. Tests: the S1 op suite ported (incl. radius-0 bitwise identity with an explicit pivot, path
  independence, lifecycle, Selection untouched); app tests: soft off ≡ today, one History entry per gesture,
  exact cancel, `on_vertices_moved` covers the influenced set, the Move anchor is a seed, keys sticky and
  applying from the next gesture, E3 refusal visible and side-effect free. The S1 experiment stays as the
  record; its suite stays green.
- **S2b — window + measurement.** Band overlay and preview (§5), the `soft_overlay_type` pass-through,
  `src/main.py` passes the GL class; the probe of §7.3; Manu runs it on the reference PC. **Gate** before S2c.
- **S2c — Artist practical test (Manu).** Head and body: soft on/off, the radius steps, euclidean vs geodesic
  (finger/lip effect M1/M2, grid diamond M4), smooth vs linear, W/E/R with constraints; the look of the bands;
  optionally the scale formula. Verdicts per item; the defaults (metric, curve, radius unit and steps, scale
  formula) are decided by Manu there.
- **Docs per slice:** `src/main.py` docstring, ROADMAP §7 intake, FINDINGS/README pointers, this AD's status.

After the verdict (not part of S2): the promotion AD (Q2-A vs keeping D, plus the fate of the Core's
`_weights` placeholder), Artist Input Truth entries for the keys if they are kept.

---

## 11. FINDINGS §5 — where each question is addressed

| §5 item | Here | State after this AD |
|---|---|---|
| 1 Core seam | §3 | proposed for S2 (D); promotion seam open |
| 2 Influence channel | §4.1, §4.2, §4.4 | proposed |
| 3 Defaults (metric, curve, scale formula) | §6 (the switches) | open — Artist, S2c |
| 4 Radius (unit, setting, scope) | §4.3, §6 | setting and scope proposed; unit open — Artist, S2c |
| 5 Identity gestures | §3.5 | unchanged for S2; open for promotion |
| 6 Basis contract | §1 F6, §3.5 | answered for the app path; Core wording only under A |
| 7 Changing rotation axis | §1 F6, §3.5 | answered for the app path (no tool does it) |
| 8 Symmetry combination | §8 | refused; contact points named |
| 9 Cost on the reference PC | §7 | measurement specified; `math.dist` in `src` is a separate follow-up (§12) |
| 10 Radius-0 identity with the tool's pivot | §3.5 | op-level test kept; app-path identity not required for S2 |

---

## 12. Not decided here / follow-ups

- Defaults for metric, curve, scale formula, radius unit and steps — Artist questions for S2c.
- The promotion seam (Q2-A vs D) and the Core's `_weights` placeholder — own AD after the S2 verdict.
- Symmetric soft selection (FINDINGS §5.8).
- Changing the radius during a running gesture (would need a re-evaluation from the start snapshot).
- Tweak and other consumers V1_CORE §6 names.
- **Separate follow-up (not part of S2):** a `math.dist` audit in `src` (FINDINGS §5.9, R6). New data point
  from this AD: `mesh_center_and_radius` (`mesh_geometry.py:44-46`) calls it once per vertex.
- Whether points through the mesh (depth off) stay readable at large radii — observe in S2c.

---

## 13. Review

*(Empty until the independent review. Findings and answers go here; the status line changes only with
Manu's decision.)*

---

## Appendix A — Probe P-D (shape)

Scratch script, container, run against `f65d223`; it imported the S1 modules for the comparison. Shape of the
classes it tested (helper names abbreviated):

```python
from core.operations.transform import VertexTransformOperation, rotate_around_axis

class _DSoft(VertexTransformOperation):
    _requires_pivot = False
    def _on_begin(self, context):
        params = context.params
        if "symmetry" in params: raise ValueError(...)                       # E9 / §8.2
        if self._requires_pivot and params.get("pivot") is None: raise ValueError(...)
        influence = {vid: float(w) for vid, w in params["influence"].items()}
        if set(influence) != set(context.selection.vertices): raise ValueError(...)
        super()._on_begin(context)                                           # Core snapshot, pivot
        self._influence = influence
        self._start = {vid: context.target.vertex_position(vid) for vid in influence}

class DMove(_DSoft):
    def _transform_position(self, pos, delta, vertex_id=None, **_):
        w = self._influence[vertex_id]
        if w != 1.0: delta = (w * delta[0], w * delta[1], w * delta[2])
        return (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])     # = core/operations/move.py:110

class DRotate(_DSoft):
    _requires_pivot = True
    def _transform_position(self, pos, axis, angle, vertex_id=None, **_):
        w = self._influence[vertex_id]
        return rotate_around_axis(pos, self.pivot, axis, angle if w == 1.0 else w * angle)

class DScale(_DSoft):
    _requires_pivot = True
    def _on_begin(self, context):
        super()._on_begin(context); self._total = (1.0, 1.0, 1.0); self._basis_set = False
    def _on_update(self, factor, basis=None, **kw):
        # one basis per gesture (L5); accumulate the total factor; then the Core loop
        ...; super()._on_update(factor=factor, basis=basis, **kw)
    def _transform_position(self, pos, factor, basis=None, vertex_id=None, **_):
        w = self._influence[vertex_id]
        if w == 1.0: return scale_apply(self.pivot, pos, triple(factor), basis)   # copy of ScaleOperation._apply
        g = tuple(1.0 + w * (t - 1.0) for t in self._total)                       # linear formula (S1 default arg)
        return scale_apply(self.pivot, self._start[vertex_id], g, basis)          # absolute for w < 1
```

## Appendix B — Probe P-V (procedure)

Scratch script, container (Linux, Python 3.13.16), against `f65d223`. Per asset × radius (5/15/30 % of the
bounding radius from `mesh_center_and_radius`) × metric: a fresh `Application`, `init_scene("obj", …)` with the
default `TraceStore`, `frame_scene()`, `set_viewport_size(1280, 800)`, optionally
`viewport.set_display(True, True, False)` (edges shown); seeds as `probe_cost.pick_seeds`; the influence map
from S1 `compute_influence`; `selection` set to exactly the influenced vertex set in vertex mode;
`key_press(W)`; 200 × `pointer_motion(640, 400, ±3, ±1)` (direction reversed half way), each followed by
`viewport.sync()`; `key_release(W)`. Statistics over moves 2–200 (the first move contains `begin`): median,
nearest-rank p95, max. Profile: `cProfile` over 200 such moves, body mesh, 30 %, euclidean.
