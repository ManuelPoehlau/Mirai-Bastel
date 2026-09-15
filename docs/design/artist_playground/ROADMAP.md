# Artist Playground — Roadmap

**Status:** Active research / implementation
**Date:** 2026-09-15
**Source of truth:** current Playground code + experiment assets; this roadmap must not describe planned work as missing when it already exists in the repository.

---

## Development Model

The Artist Playground follows a research-first model, not a feature-delivery model.

```text
Question
    ↓
Playground experiment
    ↓
Variant / setting
    ↓
Manuel plays with it
    ↓
Observation / Artist Verdict
    ↓
Candidate
    ↓
Production
```

**Production is not where we discover what is good. Production is where we cleanly implement what has already proven itself.**

The roadmap is therefore a research roadmap, but its status sections must reflect the actual repository state. Research documents may remain open-ended; implementation status must be factual.

---

## Current Repository Snapshot — 2026-09-15

The original 2026-09-10 roadmap is now substantially behind the implementation. In particular, the following are already present in `playground/`:

- Experiment Host / Slot infrastructure.
- Viewport presentation variants.
- Selection experiments including Replace, Toggle, Modifier, Box Select and Face Select.
- Transform experiments including Move, Rotate, Scale and interaction-style variants.
- A topology experiment family.
- Topology mutation tools: Extrude, Connect Edges, Loop Insert and Loop Slide.
- Topology query/selection support: Loop/Ring Select.
- A Tweak experiment family with multiple interaction variants and decision/handoff documentation.
- Headless tests for the above areas.

Therefore, **Topology Lab is not a future empty work package** and **Tweak is not an unimplemented idea**. They are existing Playground research assets whose runtime/Host integration and research status may still evolve.

This distinction is important: an experiment family existing in the repository does not mean that its UX verdict is final, nor that it belongs in Production.

---

## Dependency / Research Order

The original strict linear dependency has been relaxed because the Playground is now a multi-family research workshop.

```text
WP-AP-01 Foundation                         ✓ done
        │
        ▼
WP-AP-02 Experiment Host                    ✓ done
        │
        ▼
WP-AP-02.5 Viewport Presentation Lab        ✓ done
        │
        ├───────────────┬───────────────────┬───────────────────┐
        ▼               ▼                   ▼                   ▼
   Selection Lab   Transform Lab      Topology Lab         Tweak Lab
     AP-03             AP-04             AP-05          research family
        │               │                   │
        └───────────────┴───────────────────┴───────────────┐
                                                            ▼
                                                Artist Research / Verdicts
                                                            │
                                                            ▼
                                                      Production candidates
```

Families may be researched in parallel. A decision in one family must not silently become a setting or dependency of another family unless that relationship is explicitly part of the experiment.

---

## WP-AP-01 — Artist Playground Foundation ✓

**Status:** Done.

The Playground runs as a lightweight artist-facing experiment host with camera/navigation, mesh loading, HUD, rendering and headless-testable infrastructure.

Validated/reused foundations include:

- Playground window/app orchestration.
- Orbit camera, picking and mesh loading.
- Production viewport/core access through adapters rather than rebuilding Production systems.
- Head and cube test scenes.
- Presentation/HUD infrastructure.

Production `src/core/` and `src/viewport/` remain protected boundaries. The Playground adapts and experiments around them.

---

## WP-AP-02 — Experiment Host ✓

**Status:** Implemented and tested.

The repository contains an `ExperimentSlot` abstraction with variant identity and decision state (`UNDECIDED`, `KEEP`, `ITERATE`, `REJECT`) plus per-experiment decision documentation.

The Host is research infrastructure, not a final production tool framework.

**Important current limitation:** the Host abstraction and the runtime window are not yet equivalent concepts. Some experiment families/variants are still routed through direct Playground runtime handlers rather than being uniformly instantiated as independent runtime slots. This is an integration/design issue, not evidence that the experiment family itself is missing.

---

## WP-AP-02.5 — Viewport Presentation Lab ✓

**Status:** Done.

The Playground supports multiple presentation variants, including smooth/flat shading, wireframe, vertices and combinations thereof. Presentation is available as a controlled setting for other experiments.

---

## WP-AP-03 — Selection Lab

**Status:** Implemented baseline + extended research variants; not a final UX verdict.

Selection infrastructure and variants now exist beyond the original Phase 0–2 roadmap snapshot.

Present experiment assets include:

- Replace selection.
- Toggle selection.
- Modifier selection.
- Box Select.
- Face Select.
- Selector/picking integration and hover feedback.

The original roadmap statement that the Picking → Selection connection was still missing is **obsolete**.

### Research questions remain open

- What selection semantics feel natural?
- What should modifiers mean?
- How should box/lasso/paint-like selection behave?
- How should selection persist across operations?
- How should selection interact with transform and topology tools?

Selection variants remain research material until an explicit Artist Verdict promotes one to candidate status.

---

## WP-AP-04 — Transform / Tool Variant Lab

**Status:** Active / implemented experiment material.

The Playground already contains transform variants and runtime transform behaviour for:

- Move.
- Rotate.
- Scale.
- Hold-based interaction.
- Press/mode and press-drag/click interaction variants.

The current implementation must not be interpreted as a final answer to the Transform interaction grammar. In particular, the fact that `Move`, `Rotate` and `Scale` work is implementation evidence, not an Artist Verdict.

Current research should remain decoupled from Selection choices unless the experiment explicitly focuses on their interaction.

Known runtime behaviour to keep visible during future research: held transform keys can currently take precedence over camera navigation. This is an interaction observation/issue, not a reason to rewrite the camera system.

---

## WP-AP-05 — Topology Lab

**Status:** Active and substantially implemented in the Playground.

Topology is **not missing**. The Playground currently contains topology experiment assets and mutation tools sufficient for real mesh editing during research.

### Implemented topology capabilities

- **Extrude** — baseline and multi-face/region behaviour.
- **Connect Edges** — including the current enablement port and free-connect case.
- **Loop/Ring Select** — query/traversal based selection.
- **Loop Insert** — topology mutation through the existing topology operation path.
- **Loop Slide** — interactive drag-based loop movement with snapshot/commit/cancel and Undo/Redo.

The current topology tests cover commit/cancel/history and important geometry/topology cases. The latest roadmap work also includes the Loop Slide direction-consistency fix and regression coverage.

### Important research boundary

These tools are **Playground research implementations**, not a declaration that all topology semantics are ready for Production. Some behaviours are deliberately scoped or excluded, for example boundary-loop continuation, open-loop slide behaviour, even-spacing/clamping modes, and other unresolved interaction questions.

The Playground is therefore already capable of the kind of workflow relevant to EX-A:

```text
articulate / inspect
        ↓
recognize a topology or form problem
        ↓
change topology in the Playground
        ↓
articulate / inspect again
```

EX-A does not need to fake the modelling step by asking the artist to merely write down what they would change if the existing topology tools are sufficient for the observation.

---

## Tweak Lab — Existing Research Family

**Status:** Existing experiment material; research/Host integration still evolving.

The repository contains a dedicated `playground/experiments/tweak/` family with multiple interaction variants and research/decision handoff material.

This means **Tweak/Soft-Selection-style interaction must be audited from the current code before being described as missing**.

Its existence does not imply that it is the same thing as deformation/articulation. A topology-preserving Tweak and an EX-A bend probe are separate research questions unless an experiment explicitly combines them.

---

## EX-A — “Bend Probe” (Character Systems Research)

**Status:** Discovery / experiment design. No implementation decision yet.

Origin: `CHARACTER_SYSTEMS_RESEARCH.md`, Axis 6, sub-hypothesis 6a.

### Research question

> Does having temporary articulation available during modelling make topology/form problems visible earlier, while the mesh is still cheap to change?

### Current scope implication

Because the Playground already supports real topology editing, EX-A does **not** need to be reduced to “bend and write down what you would change”. Actual topology edits may be part of the observation when they occur naturally.

The focal variable remains the availability of temporary articulation. Selection, topology operation, presentation, camera and other settings should remain controlled unless explicitly under study.

### Still open

- What kind of bend is useful: true rotational/bending behaviour versus soft/falloff displacement?
- How long must a bent state remain inspectable?
- How should the temporary deformation return to rest?
- How is the pivot determined/signalled?
- Can the artist distinguish deformation artefacts from genuine topology problems?
- Does the artist actually use the bend during normal modelling?

The existing rigging/skinning/morphing experiment remains a separate technical research track. EX-A should not pull that system into the Playground unless the minimum viable bend probe demonstrably requires it.

---

## Documentation / Reality Rule

The following rule is now explicit for Playground documentation:

> **When implementation and roadmap disagree, inspect the current code and tests before declaring a capability missing.**

Roadmaps describe intent and research order. They are not an inventory of what exists.

In particular, do not infer “not implemented” from an old AP phase number. Check:

- `playground/experiments/`
- `playground/topology_tools/`
- `playground/window.py`
- `playground/slot.py`
- `playground/tests/`
- the relevant experiment/decision documents

This prevents stale planning documents from causing duplicate implementation or unnecessary rebuilding.

---

## Invariants for All Playground Work

```text
🏭 src/core/       → protected; change only with explicit Production decision
🏭 src/viewport/   → protected; Playground wraps/adapts rather than rebuilds
🧪 Playground     → experiments may be rough, local and reversible
📝 Research docs  → questions and observations, not hidden implementation decisions
✅ Tests           → remain green
```

Most importantly:

> **Don't rebuild if it is already validated, documented, and working. Nutzen/adaptieren, nicht neu machen.**

---

## Relationship to the Main Project Roadmap

The Artist Playground is a research initiative that feeds the main production roadmap (`docs/architecture/ROADMAP.md`).

A Playground capability is not automatically a Production feature. A successful experiment becomes a candidate only after an explicit research/Artist verdict and an implementation review.

The Playground exists to answer questions cheaply, visibly and reversibly before Production architecture is changed.