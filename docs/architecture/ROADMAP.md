# Mirai-Bastel — Architecture & Development Roadmap

**Status:** Roadmap V1.1 — updated to reflect actual repository state and to add the Integration Track (Stage B)
**Date:** 2026-10-12 (V1.1 written 2026-09-26; the summary sections §2, "Current development direction" and §14 were re-reconciled against the intake log on 2026-10-12; the intake log ([WP-06_INTAKE_LOG.md](WP-06_INTAKE_LOG.md)) is the authoritative per-slice record)
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
- **Stage A Production Entry Point** (`src/main.py`): real window, camera navigation, real Core→Viewport→GLRenderStore draw path — read-only *at that date* (2026-09-25); mutation arrived with WP-06 Stage B (below)
- AD-017 Knife/Cut system, promoted Core exception `split_edge(edge_id, t)` (2026-09-22)
- WP-STAB stabilization pass on Playground selection/overlay/history edge cases (2026-09-23)
- WP-SYM-01 / WP-SYM-LAB-01 Symmetry Lab, Slices 1–7 (definition, correspondence, symmetric Move, mirrored Knife) — Core exceptions AD-SYM-01/02. **Since superseded in structure:** WP-SYM-LAB-03 (closed 2026-10-03) rebuilt the Lab on the Production app path and deleted the old renderer/mirrored Knife; AD-SYM-03 slices 3a–7 (symmetric Connect, Delete/Dissolve, Split, Knife, Extrude) followed in the Lab (2026-10-08/09). Symmetry is in the app since AD-SYM-04 slice A1 (2026-10-14: Shift+S sets and cycles the definition in `src/main.py`, all coordinated tools run); since slice A2 (2026-10-14) the app also draws the plane outline and the problem markers (S-2; `mirai.symmetry_display`, moved from the Lab); the decision of 2026-10-02 (stay in the Lab) is superseded by Manu's decision of 2026-10-14 (Symmetry goes into the app, then symmetric Soft Selection; decided in [AD-SYM-04](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md)); status per slice in the intake log ([WP-06_INTAKE_LOG.md](WP-06_INTAKE_LOG.md)), the Lab README and `docs/ATELIER.md`
- WP-SHADE-LAB-01 Viewport Shading Lab, Slice 1 (Key+Fill worklight, 2026-09-26) — no later slice committed as of 2026-09-29; its rig is in the app since 2026-10-15 (`src/viewport/light_rig.py`, see the WP-06 intake log)
- **WP-06 Stage B** in `src/main.py`: slices B1–B8 (head scene, vertex selection, Move/Rotate/Scale on W/E/R, display modes, component modes, contextual `C`, Knife, pick cache + occlusion), then B9 Face Extrude, WP-KNIFE-01 (One Knife S1–S4, UX2), WP Delete/Dissolve, WP-SOFT-01 Soft Selection (capability promoted 2026-10-11, keys/look `PROVISIONAL`) and a temporary scene loader (`PROVISIONAL`, 2026-10-11). Verdict state per slice is **only** in the WP-06 intake log ([WP-06_INTAKE_LOG.md](WP-06_INTAKE_LOG.md)) (e.g. B6 selection-restore, B8, B9, WP-KNIFE-01 S2–S4/UX2 KEEP; Delete/Dissolve and the scene loader without an Artist verdict; B5a.1 and the worklight built 2026-10-15, verdict pending)
- **Knife Face Cut Lab** (engines frozen as the equivalence oracle in `experiments/knife_oracle/` since 2026-10-21; the Playground no longer hosts the Knife) — Lab verdicts 2026-09-29: B REJECT, D KEEP (superseded by Q5), Q5 (cross-face) KEEP. **Lab verdict only, not a promotion**; Face Holes set aside by the Artist (bridges for now). Authoritative record: `docs/research/topology/KNIFE_FACE_DECISIONS.md`
- Concave n-gon triangulation fix (ear clipping) in `src/viewport/derived.py` and its consumers (2026-09-29, found through the Face Holes discovery)

`src/core/` is deliberately conserved/frozen, with the above exceptions each individually documented in `CORE_V1_FREEZE.md` §7.1. Experiments may reveal requirements for future Core changes, but experiment code does not become production architecture automatically.

### Current development direction

The project has moved past the editor-boundary foundation: Stage A gave it a real production window (read-only at first; editing followed with Stage B). Research tracks run in parallel in the Playground (Symmetry, Shading, Knife Face Cut, and the older Topology/Tweak families), each producing candidates that are individually decided (KEEP/ITERATE/REJECT) but that had **no single place where decided candidates are assembled into the running app**.

That gap is why the **Integration Track (Stage B, WP-06 below)** exists, and it is now in progress: it pulls already-decided Playground/Lab results into `src/main.py` incrementally — one small, real capability at a time — rather than waiting for every open research question to close first. Slices B1–B9 and the follow-on packages listed under "Completed / established" are in `src/main.py` (see the WP-06 intake log ([WP-06_INTAKE_LOG.md](WP-06_INTAKE_LOG.md)) for the verdict state of each). See §7a.

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

**Decision document:** [AD-021 — Object / Component Model](AD-021-OBJECT-COMPONENT-MODEL.md) (DECIDED 2026-10-15: go for slice M0; slices M0–M2 in its §6). M0 (Core) implemented 2026-10-15; M1 (App: second object as Reference, mode `4`) implemented 2026-10-15 ([§6.1](AD-021-OBJECT-COMPONENT-MODEL.md#61-m1-implementation-note-2026-10-15)); Q-11/Q-12 answered. M2 handoff: [AD-021_M2_CLAUDE_CODE_HANDOFF](AD-021_M2_CLAUDE_CODE_HANDOFF.md); M2-0 (Reference Ghost) and M2-1 (placement in draw/component paths) implemented 2026-10-15; M2-2 (object move/rotate/scale in mode `4`, [§6.4](AD-021-OBJECT-COMPONENT-MODEL.md#64-m2-2-implementation-note--moving-rotating-scaling-objects-in-mode-4-2026-10-15)) implemented 2026-10-15; M2-3 (Apply / Clear transform, [§6.5](AD-021-OBJECT-COMPONENT-MODEL.md#65-m2-3-implementation-note--apply--clear-transform-2026-10-15)) implemented 2026-10-15; M2-4 (switching the edit object, [§6.6](AD-021-OBJECT-COMPONENT-MODEL.md#66-m2-4-implementation-note--switching-the-edit-object-2026-10-15)) implemented 2026-10-15 — M2 built, Manu's practical tests pending.

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

**Status:** Gates 3–7 done (Application orchestrator, Viewport v0.2; see §2). Text of 2026-09-04 said "gates 3–12 queued"; Gates 8–12 were never defined (`PRODUCTION_ENTRY_POINT_STAGE_A.md`), and the production window since grew through WP-06 instead.

**Key deliverables:**
- Application lifecycle + command dispatch
- Tool framework + interaction patterns
- Viewport v0.2 (incremental updates, persistent GPU resources, overlay selection)
- Input bindings + configurable hotkeys

**Scope change from original plan:** WP-04 rescoped from "Deformation Foundation" to "Production Foundation" (application-level infrastructure) after Gate 2 discovery. Deformation/rigging moved to later WP (WP-05+).

**Reference:** `docs/archive/early_work_packages/WP-04_GATE_PLANNING.md` (v2.0, post-audit), `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md`

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

The dated entries (2026-09-26 to 2026-10-11) are frozen in [WP-06_INTAKE_LOG.md](WP-06_INTAKE_LOG.md). No new per-slice entries here (AGENTS.md §4b); slices are recorded in Git and the area README, decisions in ADs.

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

Every substantial implementation package should be defined before work starts using this structure.
A Work Package doubles as a handoff once it goes to Claude Code, so it carries the same **An:** /
**Modell/Effort:** header line as the `*_CLAUDE_CODE_HANDOFF.md` documents (see precedent in
`docs/architecture/WP-SYM-LAB-01_SLICE*_CLAUDE_CODE_HANDOFF.md`): name the model (Sonnet/Opus) and
effort level, with a short reason when deviating from the default effort — Core changes, several
interacting element types, or topology edge cases typically warrant `high` or `xhigh` over the
Claude Code default.

```text
# Work Package: WP-XX

**An:** Claude Code
**Modell/Effort:** <Sonnet|Opus>, effort `<level>` (Begründung, falls vom Default abweichend)

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
- **Stage A — Production Entry Point** (`src/main.py`): window, camera, real rendering — **DONE 2026-09-25**; read-only by scope at that time (editing is WP-06 Stage B)
- AD-017 — Knife/Cut system (Core exception: `split_edge(t)`)
- **WP-06 Stage B** in `src/main.py` — B1–B9, One Knife (WP-KNIFE-01), Delete/Dissolve, Soft Selection (WP-SOFT-01) and the temporary scene loader; see the intake log ([WP-06_INTAKE_LOG.md](WP-06_INTAKE_LOG.md)) for each item's verdict state
- **Knife Face Cut Lab** — Lab verdicts 2026-09-29 (B REJECT, D KEEP → superseded, Q5 KEEP); Lab only, not promoted

## Artist Playground (active research initiative)

**WP-AP — Artist Playground**

The Artist Playground is a research-first initiative that precedes production tool decisions. Instead of implementing features and hoping they feel right, the Playground allows experimenting with variants and letting the artist decide before anything enters production.

Reference: `docs/design/artist_playground/ROADMAP.md` and `docs/design/artist_playground/ARCHITECTURE_MAP.md`

Work packages: WP-AP-01 (Foundation) → WP-AP-02 (Experiment Host) → WP-AP-03 (Selection Lab) → WP-AP-04 (Tool Variants, open) → WP-AP-05 (Topology Lab)

**Research tracks** (re-checked 2026-10-12; the Playground/Lab READMEs and `docs/ATELIER.md` hold the details):

- **Symmetry Lab** (WP-SYM-LAB-01, rebuilt on the app path in WP-SYM-LAB-03, closed 2026-10-03) — AD-SYM-03 slices 3a–7 built in the Lab (symmetric Move/Rotate/Scale, Connect, Delete/Dissolve, Split, Knife, Extrude); in `src/main.py` since AD-SYM-04 slices A1/A2 (2026-10-14, Shift+S, plane outline and problem markers; decision and slices: [AD-SYM-04](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md); next symmetric Soft Selection SS0–SS3, then A3 Re-Symmetrize after the §10 review — order Manu 2026-10-14); open Artist items in `docs/ATELIER.md`
- **Viewport Shading Lab** (WP-SHADE-LAB-01) — Slice 1 (Key+Fill worklight) committed 2026-09-26; background contrast presets still open; no later slice committed
- **Knife Face Cut Lab** (`knife_face` family, variants B / D / Q5) — Q5 = Lab KEEP (2026-09-29); integrity fix for crossing cuts and a commit-time safety net done; the cross-face Knife has since been built in Production as WP-KNIFE-01 (S1–S4, UX2; intake log ([WP-06_INTAKE_LOG.md](WP-06_INTAKE_LOG.md))); remaining Lab-side items (UX2-k earlier interior point, see `decision.md`). Face Holes discovery is archived without a decision (set aside). Record: `docs/research/topology/KNIFE_FACE_DECISIONS.md`, `docs/research/topology/`
- **Tweak Lab** — existing research family, Host integration still evolving
- WP-STAB — ongoing stabilization fixes on Playground selection/overlay/history behavior (not a Lab, but recurring maintenance across all of them)

Candidates proven in the Playground feed back into the production roadmap through **WP-06** (see the intake log ([WP-06_INTAKE_LOG.md](WP-06_INTAKE_LOG.md))).

## Next production-oriented work

1. **WP-06 — Stage B: Incremental Integration** *(top priority, in progress — B1–B9 and the follow-on packages done as listed above)*
   - Capabilities already wired into `src/main.py`: see the intake log ([WP-06_INTAKE_LOG.md](WP-06_INTAKE_LOG.md)) (selection, Move/Rotate/Scale, display and component modes, contextual `C`, One Knife, pick cache + occlusion, Face Extrude, Delete/Dissolve, Soft Selection, scene loader)
   - Open items (the Artist sets the priority): Delete/Dissolve practice check; Symmetry into the app, then symmetric Soft Selection incl. the one Core change (Manu 2026-10-14, order and slices in [AD-SYM-04](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md); AD-020); Viewport performance on large meshes (WP-VIEW-PERF-01, awaiting Manu's Intent answer). The One Knife (formerly "candidate: Knife Face Cut Q5") is built — see WP-KNIFE-01
   - Purpose unchanged: pull in only what already has an Artist verdict, one slice at a time; see the WP-06 entry in §7 for scope/non-scope

2. **WP-01 — Production Viewport Foundation** — superseded in practice by Stage A; no further separate work expected here beyond what WP-06 needs

3. **WP-03 — Transform Foundation** — Move/Rotate/Scale exist as Core operations and are in the production app since WP-06 B3/B4 (`PROMOTED`, Transform Lab verdict); no new Core work expected

4. **WP Toolbox Gaps** — Collapse V/E/F, Select Through, World/Normal transform space, Grow/Shrink, Loop-Extend, Next/Prev Loop, Relax/Smooth, Subdivide; planned 2026-10-23 in [WP_TOOLBOX_GAPS_PLAN.md](../WP_TOOLBOX_GAPS_PLAN.md) (order A1 → A2 → B1 → C1 → C2 → B2)

Modeling / Topology Expansion (Loop Insert, Loop Slide, Connect Edges, Knife, Knife Face Cut) remains a parallel research track, feeding WP-06 the same way Symmetry and Shading do.

## Strategic research / gates

- **ARCH-01 — Object / Component Model** — [AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) (DECIDED 2026-10-15; M0, M1, M2-0, M2-0…M2-4 implemented 2026-10-15; Manu's practical tests pending)
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

This roadmap is V1.x, not immutable.

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
