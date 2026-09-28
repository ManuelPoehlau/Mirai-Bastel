# Mirai-Bastel — Architecture & Development Roadmap

**Status:** Roadmap V1.1 — updated to reflect actual repository state and to add the Integration Track (Stage B)
**Date:** 2026-09-26 (previously 2026-08-29, §14 last touched 2026-09-04)
**Branch:** `main`

This document records the architecture and dependency roadmap developed in Phases A–F. It is the canonical roadmap for the project. It is intentionally a dependency- and work-package-oriented plan, not a feature checklist.

> **Project principle:** Capture first. Discuss second. Decide third. Implement fourth.
>
> **Core principle:** Implement little. Assume much.

---

## 1. Purpose

Mirai-Bastel aims to become a lightweight, efficient and flexible 3D modeler inspired by Mirai/N-World and partly by Wings3D, while remaining part of a larger living 3D system with future modeling, topology, rigging, morph-target and animation capabilities.

The roadmap exists to prevent local feature work from accidentally determining the architecture of later systems.

It answers:

- what larger system blocks exist;
- which blocks are foundations and which are features;
- which dependencies are hard, soft or independent;
- what can be developed in parallel;
- which architecture questions must be resolved before implementation;
- what constitutes completion of a larger work package.

This roadmap is a current architectural plan, not a promise that every future subsystem will be implemented exactly as listed. New evidence from experiments may change it through the architecture-review process.

---

## 2. Status at Roadmap V1.0

### Completed / established

- Core V1
- Scene / Mesh foundation
- Selection foundation
- Operation framework
- History / Undo / Redo
- Serialization foundation
- Viewport V1 experiment
- Picking experiment
- Loop / Ring experiments
- Topology experiments
- Connect Edges experiment / implementation
- WP-02 Interaction & Tool Framework, WP-04 Gates 3–7 (Application orchestrator, Viewport v0.2)
- AD-018 Production Draw Binding (Option B, `GLRenderStore`) — **DECIDED**
- **Stage A Production Entry Point** (`src/main.py`): real window, camera navigation, real Core→Viewport→GLRenderStore draw path — read-only, no mutation yet (2026-09-25)
- AD-017 Knife/Cut system, promoted Core exception `split_edge(edge_id, t)` (2026-09-22)
- WP-STAB stabilization pass on Playground selection/overlay/history edge cases (2026-09-23)
- WP-SYM-01 / WP-SYM-LAB-01 Symmetry Lab, Slices 1–7 (definition, correspondence, symmetric Move, mirrored Knife) — Core exceptions AD-SYM-01/02
- WP-SHADE-LAB-01 Viewport Shading Lab, Slice 1 (Key+Fill worklight) — **just started, 2026-09-26**

`src/core/` is deliberately conserved/frozen, with the above exceptions each individually documented in `CORE_V1_FREEZE.md` §7.1. Experiments may reveal requirements for future Core changes, but experiment code does not become production architecture automatically.

### Current development direction

The project has moved past the editor-boundary foundation: Stage A gives it a real, if read-only, production window. Three research tracks are now running in parallel in the Playground (Symmetry, Shading, and the older Topology/Tweak families), each producing candidates that are individually decided (KEEP/ITERATE/REJECT) but that have **no single place where decided candidates are actually assembled into the running app**.

That gap is the current priority: an **Integration Track (Stage B, WP-06 below)** that pulls already-decided Playground/Lab results into `src/main.py` incrementally — one small, real capability at a time — rather than waiting for every open research question to close first. See §7a.

**WP-01A (Basic Viewport & Input Foundation)** ist im Viewport-V1-Experiment umgesetzt und praktisch validiert: konfigurierbare Keyboard-/Mouse-Bindings über eine Mapping-Schicht (Input → Context → Binding → Command), Display-Modi (Shaded / Flat Shaded / Wireframe + Wireframe Overlay), Pan sowie Nachführung der bestehenden Selection- und Topology-Interaction. `src/core/` blieb dabei unverändert (Core-Freeze). Die konkrete Produktionsstruktur unter `src/` wird als explizite Architekturentscheidung aus diesem Stand abgeleitet (siehe §5 WP-01 und SOURCE_ARCHITECTURE.md).

Modeling / Topology remains a parallel development track.

---

# 3. System-Level Dependency Model

The current high-level dependency direction is:

```text
                         CORE V1 [FROZEN]
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
        Scene               Mesh              Selection
                              |                   |
                              v                   |
                           Topology               |
                              |                   |
                              +---------+---------+
                                        |
                                        v
                                   Operations
                                   /        \
                                  v          v
                              Modeling    Transform
                                  |          |
                                  +----+-----+
                                       |
                                       v
                                    History


       EDITOR / INTERACTION TRACK

       Production Viewport
              |
              v
          Interaction
              |
              v
             Tools
              |
              v
          Operations


       STRATEGIC ARCHITECTURE TRACK

       Object / Component Model  <--- Architecture Gate
                    |
                    +------------------+
                    |                  |
                    v                  v
               Materials           Rigging
                                       |
                                       v
                                  Deformation
                                       |
                                  +----+----+
                                  |         |
                                  v         v
                                Morph      Skin
                                  \
                                   v
                               Animation

       Topology Mutation
              |
              v
       Provenance / Remapping
              |
              +------> Morph
              +------> Skin
              +------> future topology-dependent data
```

The diagram shows responsibility and dependency direction, not a final source-directory layout.

---

# 4. Dependency Classes

The roadmap uses three dependency classes.

### Hard dependency

A system requires the other system or contract before meaningful integration is possible.

Example: a production Modeling Tool has a hard dependency on Selection, Operations and the Tool/Interaction contracts.

### Soft dependency

A system can be researched or developed independently, but integration later depends on another system.

Example: renderer/material research can proceed independently, while final integration depends on the production Viewport/Object boundaries.

### Independent

The system can be developed and tested without depending on the other system's implementation.

---

# 5. Work Packages

## WP-01 — Production Viewport Foundation

**Goal:** Turn the successful Viewport V1 experiment into a clean production-oriented viewport responsibility boundary.

### Scope

- viewport state;
- camera;
- projection;
- scene/mesh display;
- selection visualization;
- picking boundary;
- Core ↔ Viewport separation.

### Not in scope

- complete application UI;
- complete tool framework;
- future renderer architecture;
- speculative Object/Component framework.

### Dependencies

- Core / Scene / Mesh — **Hard**
- Selection — **Hard**
- Camera / projection concepts — **Hard**
- Tool system — **Soft**

### Enables

- production interaction;
- production picking;
- visual verification of tools;
- later application/editor integration.

### Verification

Automatic tests should cover the non-GPU-dependent parts of camera/projection/picking and state behavior. Practical verification must include display, orbit, zoom, picking and selection visualization in the real viewport.

### Definition of Done

The viewport is an independent layer that can display and interact with Core data without making the Core depend on rendering or UI code.

---

## WP-02 — Interaction & Tool Framework

**Goal:** Establish one consistent path from user input to domain operations.

```text
Input -> Interaction -> Tool -> Operation -> History/Core
```

### Scope

- tool lifecycle;
- activation;
- input routing;
- modal state;
- preview/update;
- commit;
- cancel;
- keyboard/mouse routing;
- shortcut boundary;
- Tool → Operation integration.

### Dependencies

- Interaction / Viewport — **Hard**
- Operations — **Hard**
- Selection — **Hard**
- History — **Hard for committed editing**

### Enables

- modeling tools;
- transform tools;
- consistent cancel/commit behavior;
- consistent undo boundaries.

### Verification

Automatic lifecycle tests must prove that cancel causes no committed mesh change and commit creates exactly the intended history action. A practical Move-tool test should cover selection, activation, live update, commit, undo and redo.

### Definition of Done

Interactive tools use one consistent lifecycle and do not implement their own incompatible input/commit/history machinery.

---

## WP-03 — Transform Foundation

**Goal:** Establish a reusable transform concept instead of implementing Move, Rotate and Scale as unrelated features.

### Scope

- translation;
- rotation;
- scale;
- transform context;
- coordinate-space concept;
- pivot concept;
- axis constraints where justified by the current editor needs.

### Dependencies

- Selection — **Hard**
- Operations — **Hard**
- History — **Hard**
- Tools — **Soft during isolated development, Hard for editor integration**

### Enables

- component transforms;
- object transforms after the Object Model decision;
- bone transforms;
- animation transforms.

### Verification

Automatic tests for translate/rotate/scale, multi-selection, cancel, commit, undo/redo and history boundaries. Practical viewport tests must cover all supported transform modes.

### Definition of Done

Transform behavior is a reusable domain capability that can be driven by different tools and later consumers.

---

## MODELING TRACK — Topology / Modeling Expansion

This is a **parallel track**, not a single feature ticket.

### Goal

Continue building topology and modeling capabilities as cohesive technical groups, using experiments to discover actual Core requirements.

### Current examples

- Loop / Ring selection;
- Connect Edges;
- future Loop Insert;
- Extrude;
- Inset;
- Bevel;
- Bridge;
- Slide;
- other topology-preserving or topology-changing operations as justified.

### Dependencies

- Mesh / Topology — **Hard**
- Selection — **Hard**
- Operations — **Hard**
- History — **Hard**
- Tool framework — **Soft for algorithmic experiments; Hard for production interaction**
- Viewport — **Soft for development; required for practical editor verification**

### Core rule

If a modeling experiment discovers that a production Core primitive is missing, the requirement is first demonstrated and documented in the experiment. A production Core change is then an explicit architecture decision, not an automatic side effect of the experiment.

### Verification

Modeling packages require topology invariants, element counts, connectivity, identity/ID behavior, invalid-input tests, history tests and practical viewport verification.

### Definition of Done

A modeling group is complete only when its topology behavior, history behavior and relevant architecture contracts are tested and at least one real viewport workflow has been verified.

---

# 6. Architecture Gates

## ARCH-01 — Object / Component Model

This is an architecture decision, not a feature ticket.

### Question

Should the production scene remain approximately:

```text
Scene -> Mesh
```

or evolve toward something such as:

```text
Scene -> Object -> Components
                     |
              +------+------+
              |      |      |
            Mesh  Transform ...
```

The final structure must be driven by actual requirements, especially multiple objects, object transforms, materials, rigging and animation.

### Must answer

- What is an Object?
- Who owns Geometry/Mesh?
- Where does Transform live?
- How does component selection relate to object selection?
- How are identities assigned?
- How does History operate across objects/components?
- What future Deformation/Rigging integration does the boundary permit?

### Completion

A reviewed architecture decision and canonical documentation. Code is not required merely to close this gate.

---

## ARCH-02 — Topology Identity / Provenance / Remapping

This is the second strategic architecture gate.

### Question

What information is required when topology changes?

```text
Topology mutation
       |
       v
identity / provenance information
       |
       v
future remapping or invalidation
```

Stable IDs alone are not assumed to solve future Morph/Skin remapping.

### Must answer

- Which identities survive topology changes?
- When are new identities created?
- Can a new element record its origin?
- Which dependent data can be invalidated?
- Which dependent data must be remapped?
- What minimum information must topology operations expose?

### Completion

A reviewed architectural model and documented constraints. Do not build a large remapping framework before real use cases justify it.

---

# 7. Production Foundation & Later Work

## WP-04 — Production Foundation (REVISED)

**Scope:** Application orchestrator, Interaction framework, Viewport v0.2 rendering architecture.

**Status:** Actively under development (2026-09-04). Architecture design complete; implementation gates 3–12 queued.

**Key deliverables:**
- Application lifecycle + command dispatch
- Tool framework + interaction patterns
- Viewport v0.2 (incremental updates, persistent GPU resources, overlay selection)
- Input bindings + configurable hotkeys

**Scope change from original plan:** WP-04 rescoped from "Deformation Foundation" to "Production Foundation" (application-level infrastructure) after Gate 2 discovery. Deformation/rigging moved to later WP (WP-05+).

**Reference:** `docs/WP-04_GATE_PLANNING.md` (v2.0, post-audit), `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md`

---

## WP-06 — Stage B: Incremental Integration into the Production App

**Goal:** Give the project one actual place — `src/main.py` — where already-decided Playground/Lab candidates land in the running app, piece by piece, instead of staying scattered across Symmetry Lab, Shading Lab, Topology Lab and Tweak Lab indefinitely.

### Why now

Stage A (window + camera + real draw path) exists and is stable. Three research tracks are simultaneously active with no shared destination for their output. The risk is not that any one Lab is unproductive — each produces real, tested candidates — but that "decided" never turns into "in the app," and the gap between Playground and Production keeps widening.

### Scope

- One first real mutation in the Production window (e.g. Move, since it already has committed Core/Tool/History support) — selection, live update, commit, undo/redo, through the real `Application → Viewport → GLRenderStore` path from Stage A.
- A visible, explicit "candidate intake" step: before something is wired into `src/main.py`, it must already carry an Artist Verdict (KEEP) from its originating Lab. No experiment is promoted merely because it exists.
- Small, sequential slices — one capability per slice, each independently shippable and revertable, in the spirit of the Symmetry Lab's own slice model.

### Not in scope

- Merging or resolving the still-open UX questions across Selection, Transform, Topology and Tweak in one sweep. Only individually decided pieces get pulled in.
- A general "promotion pipeline" framework. Start concrete (one tool at a time); generalize only if a second and third promotion prove the same shape is needed.
- Any new Lab research. WP-06 consumes Lab output; it does not generate it.

### Dependencies

- Stage A (`src/main.py`, AD-018) — **Hard**
- An explicit Artist Verdict (KEEP) per candidate, from its Lab — **Hard**
- WP-02 Interaction & Tool Framework — **Hard**

### Architecture contracts

- A promoted capability uses the existing production `Tool`/`Operation`/`History` path unchanged (per WP-02's Definition of Done) — it does not bring its own Playground-only input or commit machinery along.
- Promotion is a documented decision (a short `AD-0xx` or a dated note in this roadmap), not a silent code merge — consistent with §5 "Never silently change architecture" in `AGENTS.md`.

### Definition of Done

Move is a production-validated capability (Core/Tool/History already committed via WP-02) whose *interaction* enters `src/main.py` as `PROVISIONAL` (AD-013) — not a Lab-validated capability being promoted. At least one such capability is reachable and usable in `src/main.py`, through the real production path, with its own practical-viewport verification — and the process used to get it there is repeatable for the next candidate.

### Intake log

Two separate paths bring a capability's *interaction* into `src/main.py` (AD-013: capability promotion ≠ UX promotion):

- **`PROVISIONAL`** — a conventional, exchangeable baseline for an indispensable basic function per Artist Input Truth (`tools/Input_Mapping_Tool/artist_input_truth.json`). Not a UX decision; explicitly a placeholder, swappable via `keymap.json`/`BindingSet`.
- **`PROMOTED`** — a Lab result with an explicit Artist verdict of KEEP/DECIDED, carried over with a short note or AD.

Dated entries:

- 2026-09-26 — Slice B1: head basemesh as the default `src/main.py` scene + camera framing (view-only; no new interaction). `PROVISIONAL` groundwork for the slices that follow (B2 picking, B3 Move + Undo/Redo, B4 Rotate/Scale). Verdict: **KEEP (Manu, 2026-09-26)**.
- 2026-09-26 — Slice B2: vertex selection, Selection-Modifier variant (LMB replace, Shift add, Ctrl remove, Alt toggle; click on empty space clears, modifier click on empty space keeps) — **`PROMOTED`**, Artist Verdict KEEP from the Selection Lab (`playground/experiments/selection/decision.md`, Manu 2026-09-26). Navigation rebind per Artist Input Truth (Orbit = Alt+LMB drag, Pan = Alt+Shift+LMB drag, Zoom = wheel; RMB/MMB unbound) — `PROVISIONAL`. Click vs. drag on one physical input: AD-019.
- 2026-09-26 — Slice B2 verdicts (Manu, 2026-09-26): navigation **KEEP**, selection behaviour **KEEP**, highlight readability **REJECT** (the per-vertex face tint reads like vertex paint).
- 2026-09-26 — Slice B2b: selected vertex drawn as a small round point in the production yellow `(1.0, 0.82, 0.15)`, face tint removed — Artist-specified (Manu, 2026-09-26, A10). Vertex hover as a slightly larger, translucent pale-yellow point `(0.95, 0.90, 0.35, 0.55)`, Playground look — **`PROVISIONAL`** (no Lab verdict for hover exists; A11). Overlay representation: AD-018 addendum 2026-09-26.
- 2026-09-26 — Slice B2b verdicts (Manu, 2026-09-26): selected-vertex round point **KEEP** (remark: "maybe a touch smaller later — leave it for now"), vertex hover **KEEP**.
- 2026-09-27 — Slice B3: Move on `W` + Undo/Redo (`Ctrl+Z`/`Ctrl+Y`). Move mechanism = AD-016 D4 hold-key-hover (hold W + move the mouse transforms live, no button needed; release commits; a tap with no motion is a no-op; target = selection, else the hovered vertex, fixed at key press; Esc cancels) — **`PROMOTED`**, Artist Verdict KEEP from the Transform Lab (`playground/experiments/transform/decision.md`, WP-AP-04, AD-016 2026-09-21). The key `W` is Artist Input Truth convention (AD-013 addendum 2026-09-26), not part of the Lab verdict. Global transform defaults now W/E/R (Rotate/Scale resolve but stay inert until B4). Status feedback is a console line (`Application.status_message`, printed by `src/main.py`) — **`PROVISIONAL`** placeholder until a HUD exists.
- 2026-09-27 — Slice B4: Rotate on `E`, Scale on `R` through the same AD-016 hold-key-hover path as Move (`Application` now holds one generic armed-transform state, E28; only one of W/E/R can be armed at a time) — **`PROMOTED`**, same Transform Lab verdict (AD-016 applies to Move/Rotate/Scale identically); keys `E`/`R` are Artist Input Truth convention. Axis constraints wired from the existing tools (`space` per AD-012, no new constraint math): `X`/`Y`/`Z` = axis, `Shift+X`/`Shift+Y`/`Shift+Z` = YZ/XZ/XY plane (Blender exclude-axis convention, Artist decision Manu 2026-09-27; `artist_input_truth.json` updated from the previous plane-naming mapping); for Rotate a plane means rotation about its normal. Constraints act only between arming and the first mouse motion (the tool fixes `space` in `begin()`); later presses are ignored with a status line; the last key before the motion wins, no toggle/clear gesture — **`PROVISIONAL`** (AD-013). Open follow-ups: mid-drag constraint switching; **finding (practical test):** with no selection the target is the single hovered vertex, whose centroid pivot is the vertex itself, so hover-only Rotate/Scale changes nothing (release reports "no change", no history entry) — not worked around, left for Manu's verdict. Verdict: **pending** (Manu, practical window test).
- 2026-09-27 — Slice B4.1: constraint model switched to the Playground's sticky toggle (`playground/window.py`, WP-AP-INPUT-FIX-03 / WP-AXIS-CONSTRAINT-WIRING) — Artist decision Manu 2026-09-27, after the B4 practical test ("constraints are never set"). **Supersedes B4 E30/E31** (constraint only while W/E/R is held and before the first motion, no toggle); the B4 handoff itself stays as the historical record. Now: X/Y/Z and Shift+X/Y/Z set an independent, sticky constraint (`Application.axis_constraint`) with or without a transform key held; same key again = off, another key replaces; it survives commit, cancel and re-arming and is read at every `begin()` of Move/Rotate/Scale. A key during a running motion changes the state at once but only applies from the next gesture (`space` stays fixed from `begin()`, as in the Playground) — no rejection, no restart. Plane mapping unchanged (Blender exclude-axis). Status line `Constraint: X` / `Constraint: YZ plane` / `Constraint: none`; arm and commit lines carry `(constraint …)` when one is active — **`PROVISIONAL`**, no HUD. Not in scope: live switching mid-motion (Blender pattern A — recorded as an open question in `playground/experiments/transform/decision.md`), `K`/normal space, gizmo click as a constraint source. Verdict: **pending** (Manu, practical window test).
- 2026-09-27 — Slice B5a: display modes in the production window — `D` cycles Shaded → Flat Shaded → Wireframe, `Shift+D` toggles the wire overlay (Artist Input Truth; the old default `O` is gone), `SetShaded`/`SetFlatShaded`/`SetWireframe` dispatchable without a key; status line `Display: <label>` (e.g. `Display: Flat Shaded + Wire`). Start state unchanged (Shaded, no overlay). Reuses the existing headless `DisplayState` (WP-01A); `Application` translates it into `Viewport.set_display(show_faces, show_edges, flat)` (E36). Flat shading via screen-space derivative in `GLRenderStore`'s shader (`u_flat`, one normal per triangle — non-planar quads show their diagonal; E37). Edges as a separate line overlay `GLLineOverlay` outside `GLRenderStore`, depth-tested, faces polygon-offset while edges are shown, full rebuild per dirty frame while visible (E38–E40; AD-018 §7 extension 2026-09-27). Edge colour `(0.15, 0.15, 0.15)`, 1 px (Playground value, E41). All **`PROVISIONAL`** (AD-013). Not in scope: selection modes, edge/face picking/hover/highlight (→ B5b), per-polygon flat. Verdicts (Manu, practical window test): (a) flat shading with the triangle kink — **pending**; (b) edge readability, on the mesh and in pure Wireframe — **pending** (headless render already shows pure Wireframe as very dim on the dark background); (c) performance while moving with edges visible — **pending** (reference: ~2 ms per move frame for sync + render on the 648-edge head mesh under software GL/Xvfb).
- 2026-09-27 — Slice B5a verdicts (Manu, 2026-09-27): (a) flat shading per triangle **REJECT** — wanted is per-polygon flat as in common DCCs (no visible triangulation); deferred, no priority, open follow-up **B5a.1 Per-Polygon-Flat (touches AD-018 §5)** — not built in B5b; (b) wireframe readability **KEEP**; (c) performance **KEEP** on the head mesh, to be re-checked later with a higher poly count.
- 2026-09-27 — Slice B5b: component modes in the production window — `1`/`2`/`3` set Vertex/Edge/Face mode; each press clears selection and hover (Playground R-SEL-2), is ignored while W/E/R is held, status line `Mode: Vertex|Edge|Face`. Click selection (LMB / Shift add / Ctrl remove / Alt toggle, plain click on empty space clears), hover and W/E/R work in all three modes: one mode-dispatched picker (`picking.pick_component`, E43; `select_vertex_at` stays as a forward to `select_at`); transform target = resolved selection, else the vertices of the hovered vertex/edge/face (Playground hover fallback), status still counts vertices, constraints unchanged. Legacy keys `v`/`f` removed (Artist Input Truth defines only `1/2/3`, `F` is reserved for `navigation.frame_selection`; `runtime_ref`s in `artist_input_truth.json` already correct) (E47). Modes **`PROMOTED`** (Selection Lab KEEP, `playground/experiments/selection/decision.md` "Component Mode (1 / 2 / 3)"). Drawing: headless `SelectionOverlay.line_layers()`/`face_layers()` (E44), `GLLineOverlay` layers `wire`/`hover`/`selected` and new `GLTriangleOverlay` (E45, AD-018 §7 extension 2026-09-27 B5b); order mesh → wire → face highlight → edge highlight → points, `GL_LEQUAL`; faces get the polygon offset also while an edge highlight is drawn (without it the 1-px line z-fights with the head mesh and shows dashed — found in the headless render). Look **`PROVISIONAL`** (E46): selected faces opaque fill and selected edges 1-px lines in the production yellow `(1.0, 0.82, 0.15)` (one selection colour for all modes instead of Playground orange), hover `(0.95, 0.90, 0.35, 0.55)` blended in all modes. **Deviation from the handoff, reported:** the handoff asked for "same mode key again = no-op"; the Playground (`window.py` keys 1/2/3) clears the selection on every press, also in the active mode — per the handoff's contradiction rule the Playground behaviour was built. Also noted, unchanged (Playground/B3 behaviour): edge picking has no occlusion test (a hidden edge behind the surface can be hovered/selected, like vertices); a hover-fallback target is not drawn as selected while transforming. Not in scope: box/paint/lasso, loop/ring, frame selection, select all/invert, converting the selection on mode change, auto-wire in edge mode, B5a.1. Verdicts (Manu, practical window test): (a) edge/face picking behaviour — **pending**; (b) look: yellow face fill and 1-px lines — **pending**; (c) observation only: working in edge mode without the wire overlay — **pending**.
- 2026-09-28 — Slice B6: contextual `C` in the production window — Split / Edge Connect / Vertex Connect (Split: Edge mode, 1 edge; Edge Connect: Edge mode, 2+ edges, per-face/Wings semantics; Vertex Connect: Vertex mode, 2+ vertices, per-face cyclic pairing) — **`PROMOTED`** (Connect Lab KEEP 2026-09-21, AD-017 DECIDED 2026-09-22); `C` key = Artist Input Truth (`topology.connect`) — **`PROVISIONAL`**; status line PROVISIONAL. The mode-agnostic helpers and the three modes were moved (not copied) from `playground/topology_tools/` into `src/mirai/topology/` (`contextual_c.py`, `topology_points.py`, `connect_per_face.py`, `connect_vertices_per_face.py`, `split.py`) so Production and Playground share one implementation; Playground imports were re-pointed, its own tests stayed green with only import-path changes. `connect_per_face.py` now defines `TopologyToolError` itself (previously imported, backwards, from the rejected strip-semantics `connect_edges.py`); that module imports it from here instead. `playground/topology_ops.py::split_selected_edge` now forwards to `mirai.topology.split.split_selected_edge`. `Application._connect_command` (`src/mirai/application.py`) resolves the context via `resolve_c_context` and applies the residue per AD-017 §"Selection residue" — one `MeshStateCommand`/Undo-Redo entry per success, mesh and history untouched on rejection or no-op; ignored while W/E/R is armed (same Session Gate as the B5b mode keys). Empty selection → Knife, not built in B6 (no-op, status line `C: Knife not available yet`, per the handoff's explicit non-scope). Legacy cleanup: the `TOPOLOGY_CONTEXT` defaults for `s` (`SplitEdge`) and `c` (the old Vertex-mode/Edge-mode `Connect` split) were removed from `src/mirai/interaction/bindings.py` (superseded by the global `C`); the stale pre-AD-017 `CONNECT` comment in `commands.py` was rewritten. `k`/`l`/`r`/`alt+e` (Collapse/EdgeLoop/EdgeRing/Extrude) stay bound in `TOPOLOGY_CONTEXT`, unchanged — legacy, outside B6 scope. `S` stays unbound (Artist Input Truth lists `S` = Split, but `C` already covers it; not rebuilding a second key for the same operation). No `src/core` change (`Mesh.split_edge(t)` and `Mesh.connect_vertices` already supported everything needed, per AD-017 §4). New `tests/test_application_contextual_c.py` covers every context row incl. residue/mode, one history entry per success, Undo/Redo exactness (via `Application`, headless), rejection/no-op leaving mesh+history untouched, the W/E/R Session Gate, and that only the per-face (KEPT) result is reachable through `C` — not the rejected strip semantics — using the Connect Lab's own characteristic F-case (pentagon continuation, `docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md` F2). `playground/tests/test_input_wiring.py` and `tests/test_input_binding.py` updated for the binding change (an `s`/`SplitEdge` TOPOLOGY_CONTEXT assertion is now `None`; new assertions for the global `C`/`CONNECT`). Verdict: **pending** (Manu, practical window test, `docs/design/artist_playground/WP-AP-CUT_PLAN.md` §8 test script).
- 2026-09-28 — Slice B6 fix (found in the practical window test): splitting an edge crashed the app. Traceback: `KeyError: EdgeId(11)` in `Mesh.edge_vertices`, raised on the next frame from `RenderMesh._rebuild_resources` → `SelectionOverlay.build_highlight_flags` → `_hovered_to_vertices`. Cause: `selection.hovered` still held the handle of the edge that Split had just removed (the user hovers an edge, clicks it, presses `C`), and `build_highlight_flags` resolved selection/hover handles through `mesh.edge_vertices`/`mesh.face_vertices` **without** an `is_valid_*` check — unlike its sibling methods (`selected_vertex_positions`, `line_layers`, `face_layers`), which already skip invalid IDs. Two independent fixes: (a) `Application._notify_topology_changed()` now also re-anchors the hover (`_refresh_hover()`, the same pattern `_undo_redo` already used), so Production never leaves a stale hover behind after a topology mutation (Split/Edge Connect/Vertex Connect); (b) `SelectionOverlay.build_highlight_flags()`/`_hovered_to_vertices()` skip handles the mesh no longer knows, exactly like the other overlay methods — the viewport stays passive and cannot know Application invariants, so it skips instead of raising (AD-001: validity is asked from the mesh, never inferred from the ID). Second instance of the same class, found while reproducing: `C` → Edge Connect → `Ctrl+Z` → `W`/`E`/`R` raised `KeyError` in `resolve_selection_vertices()` (`mirai/interaction/tools/selection_helpers.py`) because Undo restores the mesh but not the Selection (the removed new edges stay selected); the resolver and the `_element_vertices` hover fallback (`mirai/application.py`) now skip invalid handles, so the arm is rejected with the normal "nothing to move/rotate/scale" status line instead of crashing. Tests: 6 new cases in `tests/test_overlay.py`, 4 in `tests/test_application_contextual_c.py` (incl. the `C` → `Ctrl+Z` → `W` path), 1 in `tests/test_tool_integration.py`. Verified against the stashed (unmodified) sources: 10 of them fail on the pre-fix code with the same `KeyError`; the remaining ones only pin unchanged behaviour (an invalid *selected* vertex was already harmless in Vertex mode, because such an ID never matches a live vertex). `resolve_selection_vertices` and `selection_normal` in the same helper module only needed the resolver fix (`space="normal"` is never set from the production window; the constraint commands map to x/y/z/xy/xz/yz only). B6 verdict stays **pending** (Manu, practical window test) — the crash occurred during that test.
- 2026-09-28 — Slice B6 follow-up, part 1 (ghost-selection prune, superseded by part 2 below same day) — historical record only. First fix attempt: `Application._prune_ghost_selection()`, called from `_undo_redo()`, removed every selected/hovered handle for which `mesh.is_valid_vertex/edge/face` was `False` after Undo/Redo, without restoring anything — the B6 crash fix above had only made consumers *tolerate* such ghost handles, which still counted in `len(selection.edges/vertices/faces)` and could make `resolve_c_context` resolve `C` to the wrong context after an Undo. Left "should Undo/Redo restore the previous Selection?" as an open Artist question — resolved same day, see part 2.
- 2026-09-28 — Slice B6 follow-up, part 2 (selection restore on Undo/Redo) — **`PROVISIONAL`**, verdict pending. Artist decision (Manu, 2026-09-28): Undo/Redo restores the Selection, not just the mesh — supersedes part 1's prune-only approach. `HistoryStack` (`src/core/history.py`, frozen) has no Selection concept and offers no hook around `push()`/`undo()`/`redo()`, so `Application` keeps its own mirror stack of `(before, after)` selection snapshots (`_selection_undo_stack`/`_selection_redo_stack`, `mirai/application.py`), one entry per `history.push()` it itself triggers — currently Split/Edge Connect/Vertex Connect (`_connect_command`, via `_record_selection_history`) and Move/Rotate/Scale commit (`key_release`); these are the only push call sites reachable from Production. `before` = selection snapshot (mode + vertex/edge/face sets, no hover) taken immediately before the mutation; `after` = snapshot taken right after (the residue selection `_connect_command` sets, or — for transforms, which never touch Selection — the same set as `before`). `dispatch_command`'s `UNDO`/`REDO` branch now calls `_apply_undo_redo()`, which pops the mirror stack in the same LIFO order as `HistoryStack`'s own undo/redo stacks (Undo restores `before`, Redo restores `after`, and a fresh `_record_selection_history` call clears the mirror redo stack exactly like `HistoryStack.push()` clears its own), then runs `_prune_ghost_selection()` unconditionally as a safety net. If the mirror is empty while History still allows Undo/Redo (a desync — e.g. a future push path not yet wired into `_record_selection_history`), nothing is restored and pruning is the sole fallback, so an unknown mutation source can never resurrect a crash, only fall back to part 1's behaviour. Restore semantics: Undo goes back to the selection as it was *immediately before* the undone command ran, which overwrites any manual selection change made *after* that command but before the Undo (not itself an undo step) — not a bug, the intended granularity for a Selection tied to Mesh-History entries, not its own history. `src/mirai/application.py` only — no `src/core` change (frozen), no Playground change. Tests (`tests/test_application_contextual_c.py`): updated the two B6 crash-fix cases to assert restore (the original, now-valid-again edges) instead of prune-to-empty; new cases cover Edge Connect → Undo → a second `C` reproducing the same Edge Connect result (not Knife), Split → Undo → Redo with mode+selection correct and no invalid handles at every step, `W` arming correctly on the restored selection after Undo of Edge Connect (supersedes part 1's "rejected" case), that Undo intentionally overwrites a later manual selection change with the pre-command state, and the mirror-desync pruning fallback. Full suite green: `tests` 859 passed (0 skipped, under `xvfb-run`; `playground/tests` also unaffected, 844 passed). **Open Artist question, still not decided here:** none for the restore direction itself, but multi-select drag/box-select interaction with restored selections after Undo (not yet built) may raise new questions later.
- 2026-09-28 — Slice B7 — Knife in Production: session engine **`PROMOTED`** (AD-017 DECIDED 2026-09-22: incremental path, in-session Undo/Redo with history isolation, Esc = discard, Enter / LMB outside the mesh = exactly one history entry, residue = the session's connecting edges selected + Edge mode); combined interaction (hover preview + press-slide-release + line preview) **`PROVISIONAL`** per Artist decision 2026-09-28 (Manu: one Knife, no variant switch); invalid-target display **`PROVISIONAL`**; Verdict: **pending**. `knife.py` and `knife_pick.py` were moved (not copied) from `playground/topology_tools/` to `src/mirai/topology/` (B6 pattern, logic unchanged); `_knife_project_locked_edge` (F1 edge lock) was extracted from `playground/window.py` into `mirai.topology.knife_pick.project_locked_edge`; the Playground re-imports both and its A/B variants are unchanged (AD-013 A2) — the only test change beyond import paths is that `playground/tests/test_wp_ap_cut_hover_followup.py` now imports the extracted function instead of its local replica (same cases). Additive engine API (Playground does not use it, so its behaviour is unchanged): `KnifeTool.start`, `KnifeTool.path_edges` (read-only) and `KnifeTool.accepts(target)` — the same acceptance rules as `click()` without mutating, used as the preview gate; `hover()` alone does not check the shared face / vertex adjacency. `Application` (`src/mirai/application.py`, section "Knife session"): `C` with an empty selection (any component mode) begins a session (replaces the B6 no-op status line `C: Knife not available yet`); while it runs, the unmodified LMB belongs to the Knife — pointer motion = hover preview (Variant A), LMB press on a valid edge locks it and the drag projects the cursor onto it however far it strays (F1), release cuts at that position or, near an endpoint, at that vertex (F2); a press+release without movement is a click at the hover position; an unlocked press that moved past the click threshold is not a click (Playground rule); a click outside the mesh commits. New in B7: a line preview from the current start to the prospective point (hover and slide). Keys: new binding context `knife` (`mirai.interaction.input.KNIFE_CONTEXT`, keymap.json-overridable) with `Enter` → new command `KnifeCommit` (Artist Input Truth `topology.knife_commit`) and `Ctrl+Shift+Z` → Redo; Esc/Ctrl+Z/Ctrl+Y come through the GLOBAL fallback and are routed to the session (also `dispatch_command(UNDO/REDO)`, so no path reaches the global history mid-session). Session Gate: every other key is ignored (W/E/R, 1/2/3, D/Shift+D, C, X/Y/Z …). Navigation (Alt+LMB orbit, Alt+Shift+LMB pan, wheel zoom) keeps working; modified LMB clicks during a session do nothing. `mirai.pyglet_input` now translates Enter / keypad Enter to `"enter"`; `src/main.py` passes the cursor position to `pointer_press`/`pointer_drag` (new optional `x`/`y`). Commit records the pre-session selection in the B6 follow-up mirror stack, so global Undo restores mesh + pre-session selection/mode and Redo restores the residue, like Split/Connect. Overlays: new tool layers (`viewport.overlay.TOOL_LAYERS`, `Viewport.set_tool_overlay`) in the existing point/line overlay classes — `tool_preview` (prospective point, hovered/locked edge, line preview) in the hover style, `tool_active` (start vertex F3, path edges) in the selected style; no new colours. The preview line layer is drawn without depth test (`PROVISIONAL`: a straight line across a non-planar quad would otherwise vanish behind the triangulated face). Render data is headless (`mirai.topology.knife_preview.KnifeRenderData`, `Application.knife_render_data`). Invalid targets (face, edge incident to the start, no shared face, vertex that is the start or adjacent to it, outside) show no preview point and no line; the locked edge stays highlighted during a slide. Status lines for begin/cut/start/reject/undo/redo/commit/cancel (console, `PROVISIONAL`). No `src/core` change. Tests: new `tests/test_application_knife.py` (46 cases: begin/no-begin, vertex → edge → edge path across three faces with mesh invariants after every cut, hover/line-preview render data, press-slide-release with the lock kept off the edge, endpoint snap → vertex connect, in-session Undo/Redo never touching a pre-existing global entry, Esc, Enter and click-outside commits, global Undo/Redo after commit, Session Gate keys, navigation during a session, invalid targets, `accepts` ≡ `click` on a screen grid), new `tests/test_gl_knife_overlay.py` (real GL: start point, line preview, path edge drawn; Esc leaves the frame pixel-identical to idle), `tests/test_application_contextual_c.py` (B6 no-op case → begins a session), `tests/test_pyglet_input.py` (Enter). `experiments/symmetry_lab/tests/test_lab_knife_window.py::test_enter_has_no_lab_input` now pins the Lab behaviour (Enter resolves to no Lab command) instead of the adapter's old non-translation. Full suite: `tests` 891 → 940 passed; `playground/tests` 844 passed (unchanged). Open questions (not decided here): behaviour of a modified LMB click during a session (the Playground counts Alt/Shift+click as a Knife click; Production ignores it); whether `Ctrl+Shift+Z` should also be a global Redo outside the session; whether invalid edges should still show a highlight; Undo/Redo is ignored while the Knife's LMB is held; the `[KNIFE]` diagnosis prints from the moved engine now also reach the Production console.
- 2026-09-28 — Slice B7.1 — Knife click-only (Variant A), Artist decision 2026-09-28, PROVISIONAL, verdict pending. After the B7 practical window test, Manu: press → slide → release (Playground Variant B, F1 edge lock) is redundant with the live hover preview, which already slides along the edge while hovering — Production Knife now uses Variant A only (hover preview + line preview, a click cuts at the previewed position); Blender-style drag cutting is a possible Knife V2 idea, not built, not prepared. Removed from `Application`: `_knife_locked_edge`, the `knife_locked_edge` property, the lock in `_knife_press`, the slide in `_knife_drag` (now only tracks distance for the click threshold), the locked branch in `_knife_release`, and `_knife_project`; the existing click rule (press+release under `CLICK_THRESHOLD_PX` = click at the cursor; a press that moved past the threshold is not a click) is unchanged. `project_locked_edge` stays in `mirai.topology.knife_pick` unchanged — the Playground's own Variant B still uses it (AD-013 A2); endpoint snap is unaffected (it lives in `knife_pick()` itself, not the removed slide). `tests/test_application_knife.py`: removed the press-slide-release cases, added a drag-over-a-formerly-lockable-edge-neither-locks-nor-cuts case and a line-preview-still-follows-hover-after-a-failed-drag regression case; the existing click-at-hover-position and unlocked-drag-is-not-a-click cases needed no change. `tests/test_application_knife.py`: 46 → 46 cases (2 removed, 2 added, net unchanged). No `src/core` change, no Playground change. Doc: AD-017 §12 addendum. Verdict: **pending** (Manu, practical window test).


---

## Later: WP-05+ — Deformation & Rigging

Deformation Stack foundation will follow WP-04 production infrastructure.

Conceptual target:

```text
Base Geometry
      |
      v
Deformation Stack
      |
      v
Evaluated Geometry
      |
      v
Viewport (WP-04)
```

### Dependencies

- Production Application (WP-04) — **Hard**
- Transform operations in Core — **Hard**
- Object/Geometry ownership — **Hard**
- Provenance/remapping decisions — **Strategic**

Production implementation should follow the relevant Architecture Gates rather than precede them.

---

## Morph Targets

```text
Base Mesh + Morph Target + Weight -> Evaluated Geometry
```

### Dependencies

- Deformation — **Hard**
- Geometry/Object ownership — **Hard**
- Provenance/remapping — **Strategic**

Morph is a later consumer, not an immediate Core foundation.

---

## Rigging Foundation

Conceptual dependency:

```text
Object Model
    |
    v
Transform
    |
    v
Rig / Bones / Pose
    |
    v
Deformation
```

### Dependencies

- Object Model — **Hard**
- Transform — **Hard**
- Deformation — **Hard**

Rigging research may proceed earlier; production rigging should not be pulled forward merely because it is part of the long-term vision.

---

## Animation Foundation

Conceptual dependency:

```text
Time
  |
  v
Animation
  |
  v
Transform / Pose
  |
  v
Deformation
  |
  v
Viewport
```

### Dependencies

- Transform — **Hard**
- Object Model — **Hard**
- Rigging — **Hard for character animation**
- Deformation — **Hard where animated deformation is involved**

---

## Materials / Renderer

This is a largely parallel track.

```text
Object -> Material -> Renderer -> Viewport
```

Research can proceed independently. Final production integration depends on the eventual Object, Viewport and Renderer boundaries.

---

# 8. Parallel Development Model

The roadmap deliberately allows several tracks to progress at once.

```text
                         Core V1 [frozen]
                               |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v
     Editor Track         Modeling Track       Architecture
          |                    |                 Research
          v                    |                    |
     Viewport                 |             +------+------+
          |                    |             |             |
          v                    |          Object       Provenance
     Interaction              |             |             |
          |                    |             +------+------+
          v                    |                    |
        Tools                  |                    |
          |                    |                    |
          v                    |                    |
      Transform               |                    |
          |                    |                    |
          +---------+----------+--------------------+
                    |
                    v
              Production Modeler
```

### Can run in parallel

- Viewport development ↔ Modeling research/implementation
- Tool framework research ↔ topology algorithms
- Transform development ↔ topology algorithms
- Object Model research ↔ editor/modeling work
- Provenance research ↔ editor/modeling work
- Materials/Renderer research ↔ most modeling work

### Should not be pulled forward without their foundations

- Production Morph
- Production Rigging
- Production Animation

---

# 9. Work Package Definition Standard

Every substantial implementation package should be defined before work starts using this structure:

```text
# Work Package: WP-XX

## Goal

## Why now

## Scope

## Not in scope

## Dependencies

## Architecture contracts

## Tests

## Practical viewport test

## Documentation

## Definition of Done
```

The **Not in scope** section is mandatory for larger tasks. It prevents an agent from silently expanding a bounded package into a larger architectural rewrite.

---

# 10. Claude Delegation Workflow

The project uses three task types.

## Type A — Implementation Package

Architecture is already decided.

Claude may analyze, plan, implement, test, verify and document within the defined scope.

## Type B — Research Package

Architecture is not yet decided.

Claude investigates the repository, experiments, external evidence where appropriate and alternatives. The output is analysis and recommendation, not an uncontrolled production implementation.

## Type C — Architecture Gate

A fundamental boundary affects multiple future systems.

Claude may provide technical analysis and alternatives. The project owner and architecture review decide the direction before implementation.

---

# 11. Standard Implementation Cycle

```text
Architecture Gate (if required)
          |
          v
   Work Package Spec
          |
          v
     Claude Analysis
          |
          v
      Plan Review
          |
          v
     Implementation
          |
      +---+---+
      |       |
      v       v
    Tests   Viewport
      |       |
      +---+---+
          |
          v
     Architecture Review
          |
          v
     Documentation
          |
          v
         Commit
          |
          v
   Progress / Roadmap Update
```

A package is not complete merely because its code works locally.

---

# 12. Verification Standard

Every substantial package should use both automated and practical verification where applicable.

### Automated

- unit tests;
- regression tests;
- topology invariants where relevant;
- identity/ID behavior where relevant;
- operation lifecycle;
- History / Undo / Redo;
- invalid-input and edge cases.

### Practical

Use a real viewport workflow to validate actual interaction, visibility, picking, selection, modal behavior and the final user-visible result.

### Architecture review

Before completion ask:

> Did this package strengthen the intended boundaries, or did it accidentally introduce a dependency that will make later systems harder?

---

# 13. Core Freeze and Experiment Policy

`src/core/` is currently a protected production foundation.

Experiments live under `experiments/` and may be pragmatic, temporary and disposable.

The accepted flow for a discovered Core requirement is:

```text
Experiment
    |
    v
Problem / requirement demonstrated
    |
    v
Document finding
    |
    v
Architecture review
    |
    v
Explicit Core decision
    |
    v
Targeted production change (if justified)
```

This policy is intentionally based on the Connect Edges experience: the experiment can prove that a primitive such as `Mesh.add_edge()` is needed without automatically turning every experimental convenience into production architecture.

---

# 14. Current Priority View

## Completed

- WP-02 — Interaction & Tool Framework
- Core V1 (frozen, with documented exceptions — see §7.1 of `CORE_V1_FREEZE.md`)
- Viewport V1 experiment
- Selection foundation and selection experiments
- History / Undo / Redo
- Loop / Ring experiments
- Connect Edges
- WP-04 Gates 3–7 — Application orchestrator, Viewport v0.2 render architecture
- AD-018 — Production Draw Binding (Option B, `GLRenderStore`)
- **Stage A — Production Entry Point** (`src/main.py`): window, camera, real rendering — **DONE 2026-09-25**, deliberately read-only
- AD-017 — Knife/Cut system (Core exception: `split_edge(t)`)

## Artist Playground (active research initiative)

**WP-AP — Artist Playground**

The Artist Playground is a research-first initiative that precedes production tool decisions. Instead of implementing features and hoping they feel right, the Playground allows experimenting with variants and letting the artist decide before anything enters production.

Reference: `docs/design/artist_playground/ROADMAP.md` and `docs/design/artist_playground/ARCHITECTURE_MAP.md`

Work packages: WP-AP-01 (Foundation) → WP-AP-02 (Experiment Host) → WP-AP-03 (Selection Lab) → WP-AP-04 (Tool Variants, open) → WP-AP-05 (Topology Lab)

**Currently active, in parallel** (as of 2026-09-26):

- **Symmetry Lab** (WP-SYM-LAB-01) — Slices 1–7 done: symmetry definition/correspondence, symmetric Move, mirrored Knife (lab-local)
- **Viewport Shading Lab** (WP-SHADE-LAB-01) — Slice 1 just started: Key+Fill worklight, background contrast presets still open
- **Tweak Lab** — existing research family, Host integration still evolving
- WP-STAB — ongoing stabilization fixes on Playground selection/overlay/history behavior (not a Lab, but recurring maintenance across all of them)

Candidates proven in the Playground feed back into the production roadmap — but see **WP-06** below: that hand-off currently has no concrete destination yet.

## Next production-oriented work

1. **WP-06 — Stage B: Incremental Integration** *(new top priority)*
   - One real, Lab-validated capability (starting candidate: Move) wired into `src/main.py` through the existing Stage A draw path
   - Purpose: stop candidates from accumulating across Labs with nowhere to land; pull in only what already has an Artist Verdict, one slice at a time
   - See the WP-06 entry in §7 above for scope/non-scope

2. **WP-01 — Production Viewport Foundation** — superseded in practice by Stage A; no further separate work expected here beyond what WP-06 needs

3. **WP-03 — Transform Foundation** — Move/Rotate/Scale already exist as Core operations and Playground tools; the open part is exactly WP-06 (getting them into the app), not new Core work

Modeling / Topology Expansion (Loop Insert, Loop Slide, Connect Edges, Knife) remains a parallel research track, feeding WP-06 the same way Symmetry and Shading do.

## Strategic research / gates

- **ARCH-01 — Object / Component Model**
- **ARCH-02 — Topology Identity / Provenance / Remapping**

## Later (after WP-06 / production foundation stabilizes)

- **WP-05+ — Deformation & Rigging Foundation**
- Morph Targets
- Advanced rigging / skinning
- Animation Foundation
- Materials / Renderer production integration

The exact next package is chosen deliberately after reviewing the current repository state and any new experiment evidence.

---

# 15. Change Policy for This Roadmap

This roadmap is V1.0, not immutable.

A new experiment, review or architectural discovery may justify a change. Such changes should be made deliberately and documented rather than silently drifting the roadmap.

The intended cycle is:

```text
New evidence
    |
    v
Roadmap / Architecture Review
    |
    v
Decision
    |
    v
Update canonical roadmap
    |
    v
Continue implementation
```

The roadmap should therefore remain a useful current map, not become a historical transcript of every discarded idea.
