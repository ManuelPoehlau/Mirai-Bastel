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

- 2026-09-26 — Slice B1: head basemesh as the default `src/main.py` scene + camera framing (view-only; no new interaction). `PROVISIONAL` groundwork for the slices that follow (B2 picking, B3 Move + Undo/Redo, B4 Rotate/Scale).

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
