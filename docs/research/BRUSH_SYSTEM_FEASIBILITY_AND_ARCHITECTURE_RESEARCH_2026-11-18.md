# Brush System — Feasibility and Architecture Research (2026-11-18)

**Status:** research and recommendation, English with a German summary. **No decision, no production code changed, no
keybinding changed, no dependency added.** First-pass record (AGENTS.md §6: later changes go into dated addenda).
**State audited:** `76759e2` on `claude/upbeat-albattani-tv3oiw` (clean working tree; the last relevant commits are
`662b1f6` Inflate / Pinch, `393e8ab` Surface Slide phase 3, `6d02450` picking on the posed surface).
**Question:** should Mirai get a unified, lightweight viewport brush system, and if so, how small can it be and where does
it fit?

**Labels.** **[V]** verified in the code at `76759e2` (file:line given) · **[C]** measured for this report in a cloud
container (Intel Xeon 2.1 GHz, 4 cores, Python 3.13.18, NumPy 2.5.3 — *not* the pinned 2.2.6; scratch scripts, not
committed, they only call production functions) · **[RPC]** reference PC (Core 2 Quad Q9550), taken from the result
files in `experiments/drag_cost/` · **[H]** assumption or estimate, never a measurement (reference-PC estimates = [C] × 3,
the factor the 2026-11-10 audit found for Python code) · **[O]** an Artist decision for Manu.
**Meshes:** `examples/meshes/gollum_20k.obj` (21,875 V) and `experiments/drag_cost/fixtures/gollum_87k.obj` (87,500 V,
the "100k" mesh of the 2026-11-10 audit). Radii are in percent of the mesh's bounding radius, the unit of
`SoftSettings` (`src/mirai/soft_selection/settings.py`).

---

## Kurzfassung für Manu (Deutsch)

- **Empfehlung: kein Brush-System, kein Sculpt-Modus.** Höchstens eine **kleine Strich-Schicht** (ein „Strich“ über die
  Fläche, der die *vorhandenen* Werkzeuge Smooth / Relax und später Inflate an der Mausposition wiederholt anwendet).
  Und auch die erst, **wenn Du nach einem kurzen Praxistest sagst, dass Dir das fehlt.**
- **Warum so klein:** Mirai hat das Fundament schon. Smooth, Relax, Inflate, Pinch, Surface Slide und W/E/R mit Soft
  Selection teilen heute bereits Radius, Abfallkurve, Maske, Symmetrie, Anzeige der Bänder, Radius per Shift+Rad im Zug,
  einen Undo-Schritt pro Geste und exaktes Esc. Das ist genau das, was ein Brush-Framework liefern würde. Neu wäre nur
  eines: **wiederholtes Anwenden entlang eines Mauswegs** statt einmal über einer Auswahl.
- **Schon heute fast ein Brush:** Ohne Auswahl wirken S, Alt+S, Shift+I, Shift+P, J und W auf den Punkt unter der Maus,
  mit Soft-Radius. „Greifen“ (W) und „Gleiten“ (J) sind damit schon Brush-artig – die brauchen keinen Strich.
- **Was nicht dazugehört:** Topologie-Werkzeuge (Knife, Extrude, Loop Insert …) – nie als Brush. Detail-Brushes (Draw,
  Crease, Polish) – dafür gibt es die ZBrush-Brücke (GoZ). Pinch Loop/Ring – die brauchen eine gewählte Linie, ein Brush
  hat keine.
- **Das eigentliche Hindernis ist Tempo, nicht Architektur:** Die Soft-Gewichte werden heute bei jedem Aufruf mit einem
  Durchlauf über *alle* Kanten des Mesh berechnet. Bei 87k Punkten kostet das im Container 50–77 ms (Referenz-PC
  geschätzt 150–230 ms) – pro Strich-Schritt wäre das unbrauchbar. Gemessen: 95–99 % davon ist der Aufbau der
  Nachbarliste, der Rest (die Umgebung selbst) kostet 0,1–3 ms. Einmal pro Geste aufgebaut, wäre es schnell genug. Diese
  Korrektur hilft **auch den heutigen Werkzeugen** (jede Soft-Geste startet dann ~50–75 ms schneller bei 87k, Container).
- **Morph, Symmetrie, Undo passen:** Ein Strich ist eine Aufzeichnung im Änderungs-Journal → ein Undo-Schritt, Esc exakt,
  im Morph-Bearbeitungsfenster (Tab) funktioniert die Übersetzung in das Target unverändert, in der Pose bleibt es
  gesperrt wie jede Positionsänderung. Symmetrie: die vorhandene Spiegelregel (eine Hälfte treibt, die andere wird exakt
  gespiegelt) bleibt; es gibt keine zweite Symmetrie-Rechnung.
- **Was ich von Dir brauche** (je ein Satz, Details §10): **O-1** Fehlt Dir ein Strich überhaupt (Praxistest §9 Phase 0,
  ca. 10 Minuten)? **O-2** Taste: Werkzeug-Taste halten + linke Maustaste ziehen (Vorschlag) oder etwas anderes?
  **O-3** Brush-Radius = Soft-Radius? **O-4** Wie stellt man die Stärke ein? **O-5** Strich bei eingeblendetem Morph
  (> 0 %): erlauben oder sperren?

---

## 1. Executive summary and Go / No-Go

**Verdict.**

| Alternative | Verdict |
|---|---|
| 3. Comprehensive Sculpt / Brush subsystem | **No-Go.** Duplicates the Soft field, the gesture lifecycle and the display that exist; detail sculpting already has a production path (ZBrush over GoZ, AD-029); contradicts Manu's brief of 2026-11-15 ("no separate sculpting system", AD-020 "Soft Inflate / Pinch"). |
| 2. Shared Brush Interaction **Framework** (registry, brush classes, settings per brush) | **No-Go as a framework.** Too much new surface for what is missing. |
| 2′. A **minimal stroke layer** (one session kind + a dab adapter over the existing plans) | **Conditional Go** — only after O-1 (Manu's practical answer that a positional stroke is wanted). Smallest thing that adds a genuinely new capability. |
| 1. Keep tools independent, improve them | **Go, now, independent of the brush question:** the field-performance fix (§4.1, §9 phase 1) and the cached symmetry correspondence. Both are technical, agent-decidable (AGENTS.md §7a) and help every existing Soft gesture. |

**Why.** Mirai's deformation tools already *are* one coherent interaction model (§2.2): a hold key arms a plan on the
selection (else the hovered element), a horizontal drag is the amount, the release commits one History entry, Esc rolls
back exactly, the Soft field / mask / symmetry rule / display / live radius are shared. Everything a "Brush Interaction
Framework" would centralise is centralised already, mostly in `GestureController` and `soft_selection`. The **one
capability that does not exist** is *accumulation along a pointer path*: apply an operation repeatedly at the surface
point under the moving cursor. That is a new **session kind**, not a new subsystem.

**What blocks it today is performance, not architecture** [C]: one Soft field at 87.5k costs 50–77 ms, almost all of it a
whole-mesh adjacency build that is repeated on every call (§4.1). Per dab that is unusable; once per stroke it is
irrelevant.

---

## 2. Current architecture assessment

### 2.1 Subsystem status

| Subsystem | Status | Evidence |
|---|---|---|
| Soft Selection field (radius, curves, metrics, Loop / Ring flow) | Production, `PROVISIONAL` look | `src/mirai/soft_selection/influence.py:191` `compute_influence`; `settings.py` (`SoftSettings`, `RADIUS_STEPS_PERCENT`, `world_radius_for`); AD-020 |
| Symmetric Soft field | Production | `soft_selection/symmetric.py` (`symmetric_influence`); AD-SYM-04 |
| Influence display (bands / face shading, looks), hover preview | Production | `soft_selection/gl_bands.py`, `gl_shading.py`; `application.py:3580` `_soft_preview_refresh`, `:3606` `_soft_preview_weights` (preview == op weights, F9) |
| Smooth / Relax | Production | `src/mirai/topology/smooth.py:89` `plan_smooth`; `src/core/operations/smooth.py:32` `smooth_positions`; `gestures.py:956` `SmoothGesture` |
| Inflate / Pinch (radial / loop / ring) | Production, `PROVISIONAL`, practical test **open** (ATELIER B16) | `src/mirai/topology/inflate_pinch.py:277` `plan_inflate`, `:296` `plan_pinch`; `gestures.py:1083` `DeformGesture`; keys Shift+I / Shift+P / Alt+P are engineering keys, not in `config/keymap.json` (`bindings.py:339`) |
| Grab / Move | Production as Soft W (and gizmo / Tweak drag) | `gestures.py:1271` `arm_transform` (hover fallback when nothing is selected); `soft_selection/ops.py` |
| Surface Slide | Production (phases 1–3, gates G1–G3) | `src/mirai/surface_slide/` (pure core + `plan.py` `SlideSession`); `gestures.py:875` `SurfaceSlideGesture`; key J (Manu 2026-11-15) |
| Paint Select (stroke of picks) | Production | `controllers/pointer_tools.py:321` `DragSelect`, `:614` `paint_at`; `viewport/box_select.py:176` `stroke_samples` (`PAINT_SAMPLE_PX = 6.0`, :32) |
| Mask Geometry, Hide, polygroup mask | Production | `src/mirai/mask.py`; `services.mask_values` |
| Change journal, one-entry gestures, exact rollback | Production, Core contract | `src/core/mesh.py:2404` `begin_change`, `:2412` `end_change`, `:2469` `rollback_change`, `:2564` `watch`; `MeshDeltaCommand` |
| Morph targets: mix picking, editing view, history translation | Production | `src/mirai/morph_targets.py:217` `TranslatingHistory`, `:251` `TargetView`; MODELING_ON_DEFORMED_SURFACES §15 |
| Posed surface picking (writes refused) | Production | `application.py:4949` `_query_cage`; MODELING_ON_DEFORMED_SURFACES §16 (b) |
| Layer gate (fail-closed operation classes) | Production | `src/mirai/layer_declarations.py:183` `_POSITION_ONLY_COMMANDS`, `:434` `view_refusal` |
| Incremental viewport update (packed arrays) | Production | `viewport.py:849` `on_vertices_moved`; `src/viewport/packed_geometry.py` (AD-032) |
| Pick cache with journal patching | Production | `src/mirai/viewport/picking_cache.py` (`PATCH_MAX_FRACTION = 0.25`); `picking.py:262` `pick_face`, `:290` `face_hit_position` |
| Viewport brush cursor (screen circle / hit-point disc) | **Does not exist** | no overlay of that kind in `src/viewport` / `src/mirai` [V] |
| Positional stroke that *edits* the mesh | **Does not exist** | — |
| Flatten, Draw, Crease, Polish | **Do not exist** (no code; `grep` finds only unrelated words) | — |
| Brush system / Sculpt mode | **Only mentioned as a speculative question** | `docs/design/UX_RESEARCH.md` §11 ("Could direct manipulation eventually become a lightweight modelling brush? … speculative"); AD-020 Inflate/Pinch ("No new brush, no second field") |

### 2.2 The interaction model the tools already share [V]

All held deformation gestures are `GestureSession` kinds in the AD-027 slot (`gestures.py:293`):

1. **Arm** on the hold key: target = resolved selection, else the hovered element's vertices (`arm_smooth` :1440,
   `arm_deform` :1475, `arm_transform` :1271). The plan (vertices, start positions, per-vertex weights, symmetry driver
   map) is computed **once, at the press**, from the press geometry.
2. **Drag = amount.** `SmoothGesture.step` (:980) turns horizontal motion into an amount and calls
   `plan.positions(amount)` — always from the press state, so the drag can go back and forth without drift. The
   pointer position itself is irrelevant (deltas, `cursor_wrap.py`: the pointer is warped at the viewport edge).
3. **Write** inside one journal opened at the first motion (`mesh.begin_change()` :986), notify the viewport per moved
   vertex (`services.notify_vertices_moved`), patch the pick cache.
4. **Release** = `end_change` → one `MeshDeltaCommand` → `history.push` (:1033). **Esc** = `rollback_change` (:1046).
5. **Soft live:** with Soft on, Shift+wheel steps the radius *during* the gesture: `reweight` (:1059) goes back to the press
   geometry, re-plans, replays the amount.
6. Weights come from one function for all of them: `GestureController.smooth_soft_weights` (:1654) = the W/E/R field.

This is a **dial** model. A brush is a **positional** model: the pointer's surface position chooses *where*, and repeated
dabs accumulate. The only positional stroke in the app today is Paint Select (`DragSelect.step` →
`paint_at(stroke_samples(last, cursor))`), which edits the selection, not the mesh.

### 2.3 Input context [V]

- **Wheel chords are all taken** in the code defaults: plain = Zoom, Shift = Soft radius, Ctrl = custom-curve shape,
  Ctrl+Shift = Loop / Ring flow (`bindings.py:431–487`). **Alt+wheel is unbound** in the code defaults and in
  `config/keymap.json` (Alt is the orbit modifier for drags).
- **Plain LMB drag** = `SELECT_DRAG` (box from empty space, paint from the mesh — Manu 2026-10-15 "Startpunkt
  entscheidet", `bindings.py:422`, `keymap.json`). A brush on plain LMB would collide with a decided binding.
- **LMB drag while a hold gesture is in the slot is refused silently** (`GESTURE_REFUSES` contains `SELECT_DRAG`,
  `SELECT_DRAG_ADD`, `gestures.py:158–191`). This combination — *tool key held + LMB drag* — is therefore free in exactly
  the context where it would mean "stroke with this tool" (§6.3).
- Precedent for "hold key + LMB": hold P + LMB click places the Working Pivot (`bindings.py`, Manu U-1).
- Persistent settings: `SoftSettings` is sticky per session; scene files save the view state (`mirai/view_state.py`)
  but not Soft settings; ImGui writes no ini (`imgui_layer.py:138`). A brush would add no new persistence need.

---

## 3. Existing reusable components

| Brush need | Existing component | Reuse verdict |
|---|---|---|
| Radius, falloff curve, metric | `SoftSettings` + `compute_influence` / `symmetric_influence` | **Reuse as is** (one field, F9 preview == op). Fix its per-call adjacency cost (§4.1). |
| Influence preview at the cursor | Soft hover preview (`_soft_preview_refresh`, bands / faces on the hovered element) | **Reuse**: it already shows the influence of the element under the cursor. Missing: a cursor circle (screen or surface disc). |
| Live radius while holding | `GestureSession.soft_live` / `reweight` + Shift+wheel | **Reuse** unchanged. |
| Mask, Hide | `services.mask_values`, `unblocked`, `mask_weights` | **Reuse** unchanged. |
| Symmetry | `SymmetryIndex` driver rule (`inflate_pinch._region` :150, `plan_smooth`), exact mirror writes, seam projection | **Reuse**; compute the index **once per stroke** (§4.3). No second system. |
| Surface hit under the cursor | `pick_face` + `face_hit_position` on the query cage (mix / posed surface), GPU or CPU | **Reuse.** The Knife already uses the same hit (`face_hit`, `picking.py:300`). |
| Stroke sampling / spacing | `stroke_samples(start, end, spacing)` (`box_select.py:176`) | **Reuse** (spacing in px; a brush would pick spacing relative to the radius, a one-line call change). |
| Operations | `plan_smooth` (Smooth / Relax), `plan_inflate`, `plan_pinch(radial)` | **Reuse** per dab (§6.2). Not reusable as dabs: Pinch loop/ring (needs a selected line), Surface Slide (fixed row set and reference per gesture), Extrude / Inset / Bevel / Knife (topology). |
| One logical undo, exact cancel | `begin_change` / `end_change` / `rollback_change`, `MeshDeltaCommand` | **Reuse**: the journal records each element's first "before" only, so a long stroke stays O(touched vertices) (measured §4.4). |
| Morph editing view | `TranslatingHistory` (one view push → one base-layer delta) | **Reuse** unchanged — requires the stroke to be one push, which it is. |
| Pose / layer safety | `layer_declarations` (fail-closed enumeration test), pose refusal (AD-028 §7.1) | **Reuse**: a new stroke command must be classified `POSITION_ONLY`; the enumeration test fails until it is. |
| Viewport update | `on_vertices_moved` → `RenderMesh` packed arrays (AD-032) | **Reuse**; cost scales with moved vertices (≈ 2.6 µs per moved vertex on the RPC, `RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md`). |
| Detail sculpting | ZBrush round trip over GoZ (AD-029: positions, polygroups, UVs, morph targets as SubTools, one Undo step on return) | **The production path** for Draw / Crease / Polish-type work. |

---

## 4. Architectural gaps and technical constraints

### 4.1 The Soft field rebuilds the whole mesh's adjacency on every call — the decisive gap

`_geodesic_distances` (`influence.py:119`) builds a neighbour map over **all** edges before its pruned Dijkstra; its
comment (:125) justifies this with "`Mesh.vertex_edges()` … is an O(E) scan in Core V1". **That premise is stale [V]:**
`Mesh.vertex_edges` now reads an index (`core/mesh.py:983`, `self._vertex_edges`). `_euclidean_distances` (:100) scans
all vertices (bounding-box reject) on every call.

Measured [C], one seed in the face region, field `geodesic` / `smooth`, median of 5:

| Mesh | Radius | Weighted V | `compute_influence` today | Region-only Dijkstra on a prebuilt map | `plan_inflate` on that field |
|---|---:|---:|---:|---:|---:|
| 20k | 3 % | 14 | 10.96 ms | 0.02 ms | 0.07 ms |
| 20k | 10 % | 208 | 9.52 ms | 0.32 ms | 1.04 ms |
| 20k | 15 % | 450 | 14.39 ms | 0.87 ms | 3.07 ms |
| 87.5k | 3 % | 56 | 53.07 ms | 0.12 ms | 0.38 ms |
| 87.5k | 10 % | 842 | 51.55 ms | 1.18 ms | 4.44 ms |
| 87.5k | 15 % | 1,808 | 54.58 ms | 2.83 ms | 9.31 ms |
| 87.5k | 25 % | 4,055 | 64.49 ms | 9.22 ms | 28.58 ms |

The whole-mesh neighbour build alone: 16.6 ms (20k), 76.9 ms (87.5k) [C]. Container noise between runs was up to ~40 %
(e.g. 87.5k / 5 %: 50.8 vs 75.4 ms in two runs); the ratio is stable: **95–99 % of the field cost is the adjacency
build, independent of the radius.** The euclidean field: 2.7–3.3 ms (20k), 10.5–17.3 ms (87.5k) [C].

Consequences:

- **Per dab, today's field is unusable at 87.5k** [H]: ≈ 150–230 ms per dab on the RPC — a stroke would run at 4–6 Hz.
- **With an adjacency built once per stroke** (topology cannot change during a stroke; positions can, and the Dijkstra
  reads current positions), a 3–10 % dab field costs 0.1–1.2 ms [C], ≈ 0.4–3.5 ms [H, RPC].
- **The same fix helps today's tools:** every Soft press (W/E/R, S, Shift+I, J) and every Soft hover-preview change pays
  the 50–77 ms [C] once. ATELIER D1f ("Symmetrie + Soft Selection auf dem Körper: über dem 8-ms-Wert ab 15 % Radius") and
  D1c are partly this cost [H].
- Constraint: the field must stay **bit-identical** (preview == op weights, F9; `tests/test_soft_selection_influence.py`,
  `test_soft_hover_preview.py`, `test_soft_flow*.py`). The Loop / Ring flow metric (`flow.py`, `flow_distances`) needs
  the same treatment. Edge-iteration order must be preserved for Dijkstra tie-breaks [H, to verify in the change].

### 4.2 No positional session kind and no cursor display

Every mesh-editing gesture is a dial (§2.2). A stroke needs: the cursor's surface hit per sample (§3), a dab loop, and a
cursor display. The display can be a screen-space circle (the ImGui foreground draw list already draws circles,
`imgui_layer.py:628`) or the existing bands at the hit. Unknown [H]: how the world radius maps to a screen circle on a
perspective view (the radius is world, `world_per_px` (`gestures.py:1119`) gives the scale at a depth).

### 4.3 Symmetry setup is whole-mesh per call

[C] at 87.5k with a definition set: `vertex_correspondence` 203 ms, `SymmetryIndex(mesh)` 781 ms (20k: 46 / 152 ms).
(The fixture is not exactly mirror-paired, so the states are all `UNPAIRED`; the cost is a full pass either way.)
`smooth_soft_weights` calls `vertex_correspondence(mesh)` directly (`gestures.py:1665`), and `plan_inflate` /
`plan_smooth` build a `SymmetryIndex` per plan, while the preview reads the cached report
(`self._symmetry.reports.current(mesh)`, `application.py:3623`). For one press this is the known AD-SYM-04 cost; for a
per-dab re-plan it is prohibitive. **Constraint for a stroke:** correspondence and the partner map once per stroke. That
is valid for the whole stroke because writes keep pairs exact (each partner written as `mirror_position` of its driver,
seam points projected onto the exact axis plane) [V for the write rule; H that no pair breaks mid-stroke — to be pinned by
a test].

### 4.4 Undo / history: no gap [V, C]

`end_change` diffs the first recorded "before" of each touched element against its current record
(`core/mesh.py:2412–2443`), so the journal grows with touched vertices, not with dabs. [C]: 200 dabs × 58 V (87.5k) in one
journal + `end_change` = 5.4 ms total, delta 58 V; 200 × 25 V (20k) = 2.1 ms. One stroke → one `MeshDeltaCommand` → one
History entry; redo replays the stored "after" records (deterministic); Esc = `rollback_change` (exact). An interrupted
gesture already ends through `cleanup` → `release_change` (`gestures.py:1050`), keeping what was written —
the same rule would apply to a stroke (open question: should a focus loss commit or roll back? Today's gestures keep).

### 4.5 Morph and pose: rules exist, one semantic question

- **Editing view (Tab):** every app tool runs on the view; `TranslatingHistory` writes the touched points' `p − b` into
  the base layer in one recording [V, `morph_targets.py` docstring]. A stroke = one push → compatible.
- **Base editing with a mix > 0 %:** hover and picks read the drawn mix, **every edit writes the rest positions**
  (§15 (a)); the Soft field is intrinsic on the rest mesh (§16 (c)). For a Smooth stroke this means: the *rest* shape is
  smoothed, the offsets stay; where offsets vary, the drawn result does not look smoothed. Same semantics as today's S at
  a mix — but a stroke invites "paint where it looks bumpy", so the mismatch is more visible [H] → **O-5**.
  Inflate normals are rest normals (`inflate_pinch._Normals`, press geometry) — same caveat.
- **Pose:** position edits stay refused (MODELING_ON_DEFORMED_SURFACES §16 (b), AD-028 §7.1); a stroke would be refused the
  same way, through the existing gate [V].

### 4.6 Other constraints

- **Pick cache:** a dab moves vertices, the next sample needs a hit → the cache patches touched vertices from the journal;
  above `PATCH_MAX_FRACTION = 0.25` of the elements it re-projects all. Brush regions are far below that [V].
- **Hover latency:** ATELIER lists "Hover-Kreis folgt auf dem Head leicht verzögert" as parked — a cursor that lags is
  worse for a brush than for selection [H]. Measure before building the cursor.
- **Pinch loop / ring** refuse without a seed line and without Soft (`plan_pinch`); not meaningful as a brush [V].
- **Surface Slide** fixes its row set and captures its reference per gesture (`SlideSession`, contract item 7, audit E1
  "pro Zug"). Adding rows mid-stroke would break the contract (no region jumps, speed limit per row) [V for the contract,
  H for the conclusion].

---

## 5. Comparison of the architecture alternatives

| Criterion | 1. Independent tools, improved | 2′. Minimal stroke layer (recommended if O-1 = yes) | 2. Brush Interaction Framework | 3. Sculpt / Brush subsystem |
|---|---|---|---|---|
| New code (order of magnitude) [H] | field cache + symmetry cache, ~100–200 lines | + 1 session kind, 1 dab adapter per op, cursor overlay, ~500–800 lines + tests | + registry, brush base classes, per-brush settings, panel, ~2–4k | own mode, own field/falloff, own undo granularity, dyntopo-like needs, 5k+ |
| Reuse of existing code | full | full: field, mask, symmetry rule, plans, journal, gate, display | partial: tempted to wrap / re-express the field and gestures | low: parallel to Soft Selection |
| Performance | improves every Soft gesture now | per-dab budget fits **after** the field fix (§8.4) | same as 2′, plus framework overhead per dab | needs its own spatial structures (BVH, dyntopo); Python per-element cost (2026-11-10 audit) makes 87.5k sculpting at dab rate doubtful [H] |
| Morph / symmetry compatibility | unchanged | unchanged — same plans, same gate, same history translation | risk of per-brush exceptions | high risk: second symmetry and second layer semantics |
| Maintenance | minimal | one more session kind in the slot (AD-027 already lists kinds) | new public contract to keep stable | a second product inside the product |
| UX | keeps one dial model; no "paint where I look" | one model: "hold the tool key; drag the dial, or press LMB and stroke" (§6.3) | settings per brush, more to learn | mode switch, contradicts "coherent modelling environment" |
| Extensibility | per tool | new dab = one adapter (Flatten later) | high, unused | high, unused |
| Fits decided direction | yes | yes, if O-1 | weakly ("no new brush", AD-020) | **no** (Manu 2026-11-15) |

---

## 6. Recommended architecture (conceptual)

### 6.1 Layers

```
 A. Stroke interaction (new, small)            B. Operations (existing, unchanged)
 ─────────────────────────────────             ──────────────────────────────────
 StrokeSession  (a GestureSession kind)        plan_smooth(relax)     → positions
   · samples: stroke_samples(spacing)          plan_inflate           → positions
   · hit: pick_face + face_hit_position         plan_pinch(radial)    → positions
     on the query cage                          (later: plan_flatten)
   · dab: seeds near hit → field → plan                ▲
          → positions at a small amount               │ called per dab through a
   · cursor display                                   │ 3-line adapter: (mesh, seeds,
                                                      │ weights, mask, strength) → {vid: pos}
 C. Shared field (existing + perf fix)         D. Commit (existing)
 ─────────────────────────────────             ──────────────────────
 compute_influence / symmetric_influence       begin_change at first dab
   + stroke-scoped adjacency                   end_change → MeshDeltaCommand → history.push
   + stroke-scoped correspondence / index      (TranslatingHistory on the editing view)
 mask_values, unblocked                        rollback_change on Esc
                                               layer gate: POSITION_ONLY; pose refused
```

- **A is the only new layer.** It owns sampling, the hit, dab spacing, the cursor display and the stroke lifecycle — the
  "brush interaction framework" of the brief, reduced to one session kind. It never computes weights or positions.
- **B stays where it is** (`src/mirai/topology/`). An operation does not know whether it runs as a dial or as a dab.
  Grab-type operations (Move, Surface Slide) are **not** dabs: their field is computed once at the press and the drag is
  their amount — they stay gestures; at most A lends them the cursor display and an "anchor at the hit point" option.
- **C is shared by both** dial gestures and strokes; the perf fix lives here (in `soft_selection`, above the Core; no
  `src/core/` change, CORE_V1_FREEZE untouched).
- **D is unchanged**: one stroke = one journal = one entry.

### 6.2 Dab semantics (the one genuinely new rule)

Today's plans compute `positions(amount)` **from the press state**. A dab instead applies a **small fixed amount from the
current state** at the current seeds: re-plan at each dab on the region around the hit (cheap after §4.1:
`plan_inflate` 0.4–4.4 ms, `plan_smooth` 0.1–0.2 ms at 5 % [C]), take `positions(strength)`, write. Drift is the intended
behaviour of a stroke; exactness is kept where it matters: Esc = rollback, Undo = one delta, symmetry pairs exact per dab.
Seeds per dab: the vertices of the hit face (or the nearest vertex), then the Soft field over them — the same seeds a
hover-armed gesture would take [H, design detail].

### 6.3 Input proposal (for Manu, nothing changed) — **O-2**

**"Hold the tool's key: drag = dial (as today); press LMB and drag = stroke with that tool at the cursor."**
S + LMB drag = Smooth stroke, Alt+S + LMB = Relax stroke, Shift+I + LMB = Inflate stroke. No new key; uses the combination
that is refused silently today (§2.3); Shift+wheel keeps stepping the radius while the key is held (exists). Open detail:
LMB while the dial has already begun → ignore (proposal). Alternatives: a brush toggle key (one more mode to remember),
or plain LMB drag on the mesh in a "brush state" (collides with Paint Select, decided 2026-10-15).

### 6.4 Topology-changing operations — excluded

They plan once on a selection, refuse by topology rules (flow, seams, layer gate rows per operation, symmetric
coordinators), and are judged by Manu by exact element results. A stroke of topology edits is unpredictable, cannot keep
`SymmetryIndex` valid across dabs (§4.3 relies on unchanged topology), and would invalidate the stroke-scoped adjacency at
every dab. **They do not belong to the stroke layer.**

---

## 7. Recommended initial Brush MVP

**Only after O-1 = yes.** Scope:

1. **Smooth stroke** (+ Relax as the Alt variant): hold S / Alt+S + LMB drag. Smooth is the most common corrective
   stroke in polygon modelling, has no sign and no direction, keeps borders fixed (`plan_smooth`), and its plan is the
   cheapest [C]. Inflate comes second (it needs a sign: drag direction or Ctrl as invert — **O-4**).
2. Radius = the Soft radius (world, % of bounding radius, the existing steps and Shift+wheel) — **O-3**; falloff = the
   Soft curve; Soft does not need to be switched on for a stroke (proposal).
3. Spacing = a fraction of the screen radius through `stroke_samples` [H: ¼ radius].
4. Cursor: a screen circle of the radius at the hit depth + the existing bands of the current dab.
5. One History entry per stroke, Esc exact, editing view through `TranslatingHistory`, pose refused, mix > 0 % per O-5.
6. Symmetry with the existing driver rule; correspondence once per stroke.
7. Not in the MVP: strength curve, pressure, stroke smoothing (lazy mouse), spacing settings UI, Flatten, select brush.

**Acceptance (proposal):** ≤ 16.7 ms p95 per dab for a 5 % radius on `gollum_20k` and ≤ 33 ms p95 on the 87.5k fixture on
the RPC (bars of the D3 gate); stroke delta == sum of its dabs; Esc bit-identical; Undo / Redo bit-identical; symmetric
pairs exact after every dab; layer values bit-identical on a layered mesh; refused in a pose; enumeration test of the
layer gate green.

---

## 8. Risk assessment

### 8.1 Morph

| Risk | Level | Mitigation |
|---|---|---|
| Stroke at a mix > 0 % smooths the rest, not the drawn shape | medium (UX) | O-5: refuse with a status line ("Tab to edit the target, N to 0 %"), or allow with today's §15 (a) semantics |
| Editing view: history translation of a long stroke | low | one push; `TranslatingHistory` writes only touched points [V] |
| Accidental write into a target / unrelated state | low | strokes write positions only; layer gate `POSITION_ONLY` contract test checks layers bit-identical [V for the test pattern] |
| Pose | none | refused like every position edit [V] |

### 8.2 Symmetry

| Risk | Level | Mitigation |
|---|---|---|
| Second symmetry system | avoided | reuse `SymmetryIndex` driver rule and mirror writes (§3) |
| Whole-mesh correspondence per dab | high if done naively | once per stroke (§4.3); partner map stays valid because writes keep pairs exact |
| Stroke crossing the plane | medium | the driver rule is per pair, not per dab; a dab on the passive side writes the driver's mirror — needs a test; O-7 |
| Unpaired seeds refuse (`DeformRefused`, `SmoothRefused`) | medium (UX) | a dab whose seeds have no partner: skip the dab silently and say it once in the status line [H] |

### 8.3 Undo / cancel

Low risk [V, C]: one journal per stroke, O(touched) memory, exact rollback, deterministic redo. Open: focus loss during a
stroke (today's gestures keep what was written) — follow the existing rule.

### 8.4 Performance budget per dab [C → H for RPC]

| Part | 20k, 5–10 % | 87.5k, 5–10 % | Note |
|---|---|---|---|
| Surface hit | GPU: 0.50 ms hover, **3.79 ms first pick after a change**; CPU: 7.07 / 143 ms [RPC p50, `RESULTS_PICKING_APP_REFERENCE_PC_2026-10-21.md`] | not measured | After a dab the mesh has changed, so a hit is closer to "first pick" than to "hover". The CPU row predates later pick-cache work; **re-measure** — the CPU fallback could dominate the dab |
| Field, **today** | 10–14 ms [C] | 50–77 ms [C] → 150–230 ms [H] | blocker |
| Field, stroke-scoped adjacency | 0.05–0.3 ms [C] | 0.2–1.2 ms [C] | after §9 phase 1 |
| Plan (Smooth / Inflate) | 0.1–1 ms [C] | 0.2–4.4 ms [C] | Inflate's `_Normals` per vertex dominates |
| Journal writes | ~0.7 µs / V [C] | same | |
| Viewport sync | ≈ 2.6 µs / moved V [RPC] | ≈ 1–2 ms for 400–800 V [H] | AD-032 arrays |
| **Total per dab after fix** | ≈ 5–10 ms [H, RPC, GPU picking] | ≈ 10–25 ms [H, RPC, GPU picking] | within 16.7 / 33 ms; 25 % radius at 87.5k (≈ 120 ms [H]) is not; with the CPU picker the hit alone may break the bar |

Large radii at 87.5k stay slow per dab [H]; a stroke would cap the dab rate (skip samples, not drop them silently: the
last sample is always applied) or cap the radius — design detail, measured during phase 2.

---

## 9. Suggested phased roadmap

| Phase | Content | Decision | Size |
|---|---|---|---|
| **0** — practical test (no code) | Manu, ≈ 10 min on `gollum_20k`: Soft on (O), nothing selected, hover the cheek; hold S and drag, hold Shift+I and drag, hold J and drag, hold W and drag; then try to fix three small bumps with S on hovered points. Question: "Fehlt Dir ein Strich, oder reicht Hover + Halten?" (O-1) | Manu | — |
| **1** — field performance (independent of O-1) | Stroke-/gesture-scoped adjacency for the geodesic and flow fields; cached correspondence in `smooth_soft_weights`; weights bit-identical (existing tests), arm time measured before / after on 20k and 87.5k; stale comment `influence.py:125` corrected | agent (AGENTS.md §7a: technical, no Artist question) — or Manu says "nicht jetzt" | M |
| **2** — stroke MVP (only if O-1 = yes) | `StrokeSession`, surface hit, spacing, cursor circle, Smooth / Relax dabs, gate classification, tests §7, D3-style probe row, practical test | Manu: O-2, O-3, O-5 | M–L |
| **3** — more dabs | Inflate (O-4 sign), Pinch radial; Flatten only on request | Manu per tool | S each |
| **4** — evidence only | Relax constrained to the surface (Surface Slide reference as projection target), a radius variant of Paint Select (all vertices within the screen radius via `PickCache.vertex_screen`), cursor display for W / J | Manu | — |

Never: detail brushes (Draw / Crease / Polish → GoZ), topology strokes, a Sculpt mode, a brush settings panel per brush.

---

## 10. Open decisions for Manu

| # | Question | Proposal |
|---|---|---|
| **O-1** | Is a positional stroke wanted at all, or are hover-armed hold gestures (exist today) enough? | Decide after phase 0 |
| **O-2** | Stroke input | Tool key held + LMB drag (§6.3); no keymap change before your "Taste passt" |
| **O-3** | Brush radius | = Soft radius (world, % steps, Shift+wheel); no separate screen-px radius |
| **O-4** | Strength and sign | Fixed small strength per tool; Inflate: Ctrl inverts during the stroke; Alt+wheel (free) for strength only if a fixed value proves wrong |
| **O-5** | Stroke at a morph mix > 0 % (base editing) | Refuse with a hint (Tab / N); today's dial tools unchanged |
| **O-6** | Does a selection limit the stroke? | No; Mask Geometry is the limit (as in every tool) |
| **O-7** | Symmetric stroke across the plane | Allowed; the driver rule decides per pair |
| **O-8** | MVP tool | Smooth (+ Relax) first, Inflate second |

## 11. What this report did not verify

- Reference-PC numbers for anything in §4.1 / §4.3 / §8.4 — only container runs; the RPC factor ×3 is the 2026-11-10
  audit's Python factor.
- A pick hit on the 87.5k fixture, and the cost of a hit right after a dab (GPU ID pass re-render, CPU pick-cache patch)
  during continuous motion — the one per-dab part with no current measurement; it could change the §8.4 totals.
- Whether bit-identical weights survive a stroke-scoped adjacency (edge iteration order) — the phase 1 change must prove it
  with the existing tests.
- How a world radius should read as a screen circle in perspective near silhouettes.
- No test suite was run: no code changed (AGENTS.md §8a).

## Sources (code)

`src/mirai/soft_selection/influence.py`, `settings.py`, `symmetric.py`, `flow.py` · `src/mirai/controllers/gestures.py`,
`pointer_tools.py`, `services.py`, `morph.py` · `src/mirai/topology/inflate_pinch.py`, `smooth.py` ·
`src/core/operations/smooth.py` · `src/core/mesh.py` · `src/mirai/surface_slide/__init__.py`, `plan.py` ·
`src/mirai/symmetry.py`, `symmetry_coordination.py`, `symmetry_display.py` · `src/mirai/layer_declarations.py` ·
`src/mirai/morph_targets.py` · `src/mirai/application.py` · `src/mirai/viewport/picking.py`, `picking_cache.py`,
`box_select.py` · `src/viewport/viewport.py`, `packed_geometry.py` · `src/mirai/interaction/bindings.py` ·
`config/keymap.json`. Docs: AD-020 (Soft Inflate / Pinch), AD-027, AD-028 §7.1, AD-029, AD-032,
`docs/design/MODELING_ON_DEFORMED_SURFACES.md` §15–§16, `docs/design/UX_RESEARCH.md` §11,
`docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md`,
`docs/research/SURFACE_SLIDE_PRODUCTION_READINESS_AUDIT_2026-11-14.md`, `docs/ATELIER.md` (B16, D1c, D1f),
`experiments/drag_cost/RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md`, `RESULTS_PICKING_APP_REFERENCE_PC_2026-10-21.md`.
