# Artist Playground — Experiment Host Audit vs. Research Map V2

**Status:** Technical assessment — no implementation performed  
**Date:** 2026-09-15  
**Author:** Interaction Dev role  
**Scope:** Current Experiment Host capability and its relationship to the Artist Playground research mode.  
**Method:** Current repository state on `main` is the source of truth. This audit supersedes the 2026-09-13 V1 audit where findings have become obsolete.

> **Reality rule:** This document describes the current implementation. Do not infer missing capabilities from an older roadmap or from the previous audit. If implementation and documentation disagree, inspect the current code and tests first.

---

## 1. Audit Result

The Experiment Host has progressed beyond the state described by the 2026-09-13 audit.

The previous audit correctly identified the need for concurrent per-family experiment state, but that gap has since been addressed in the Playground runtime. The current `PlaygroundApp` maintains a registry of experiment slots by family, and the runtime window registers and activates multiple experiment families rather than relying only on one singular Host slot.

Current experiment families wired into the runtime include:

- **Selection**
- **Presentation**
- **Transform**
- **Tweak**
- **Topology**

Topology and Tweak are therefore **not missing capabilities** and must not be treated as deferred or absent when reasoning about the current Playground.

The remaining questions are primarily about research quality, runtime interaction behaviour, completeness of individual experiment families, and whether every desired operation is exposed through the Host in the same way — not about whether the Host is still a single-slot prototype.

---

## 2. Current Host Capability

### 2.1 Experiment lifecycle

`playground/experiment.py` provides the minimal experiment lifecycle interface (`activate`, `deactivate`, `update`, `draw`).

This remains a deliberately small abstraction. Existing experiment variants should continue to reuse shared Playground state rather than duplicating selection, transform, topology, or rendering logic.

### 2.2 ExperimentSlot

`playground/slot.py` provides the per-family variant container and decision apparatus, including:

- indexed variant activation,
- `deactivate()` → `activate()` ordering,
- `Decision` states (`UNDECIDED`, `KEEP`, `ITERATE`, `REJECT`),
- decision-document generation/writing.

The Host remains a research apparatus, not a combination-matrix or dependency system.

### 2.3 Multiple active families

The previous V1 audit described a singular `_active_slot` / `_active_experiment` limitation. The current application instead supports a **per-family slot registry** and activation by family/variant.

This is important because the Research Map calls for independent dimensions that can coexist at runtime. A Selection variant can therefore be changed without conceptually replacing the Transform, Presentation, Tweak, or Topology family.

The current implementation should still be treated as an experiment host rather than as a finished production tool system: the existence of a registered variant means that it is available for observation, not that it has been validated or selected as a final UX decision.

---

## 3. Current Runtime Experiment Families

### Selection

The current Selection experiment family includes the established variants such as:

- Replace
- Toggle
- Modifier
- Box Select
- Face Select

These are part of the current Playground research surface.

### Presentation

The Presentation family is implemented and provides the current shading/display research variants.

### Transform

The Transform family is implemented with the current Move / Rotate / Scale experiment variants. The runtime still has interaction details worth observing, particularly around transform-key precedence versus camera navigation.

### Tweak

`playground/experiments/tweak/` exists as a real research family and must be treated as such. The current variants and their supporting decision/handoff documentation are evidence that Tweak/Soft-Selection research is no longer a merely proposed or missing area.

Whether the current Tweak variants are sufficient for a particular research question is a separate question and must be established by inspecting the actual variants, not by assuming that Tweak is absent.

### Topology

`playground/experiments/topology/` exists as a real research family.

The current Playground also contains runtime topology operations beyond a purely observational surface, including operations such as:

- Split Edge
- Connect Edges
- Loop / Ring selection
- Loop Insert
- Loop Slide
- Extrude

These operations are therefore available as actual topology manipulation material for Playground research where the runtime path exposes them.

**Important correction to V1:** topology is **not** a future/deferred AP-05 capability. AP-05 has become an active and substantially implemented research area.

---

## 4. Runtime Topology Path

The current runtime topology surface is not merely a set of placeholder experiment names. Topology operations can modify the mesh and feed those changes through the existing state/history mechanisms.

The current architecture includes snapshot-based mesh state commands for topology changes. Where an operation uses this path, the intended model is:

**Selection → topology operation → mesh state update → history entry → undo/redo**

This is particularly important for EX-A and related research: an artist can potentially perform an actual topology intervention after observing a problem under temporary articulation. The experiment therefore does not need to be artificially reduced to “see and name the problem” when the required topology manipulation is already available.

Individual topology operations still need to be considered separately. Not every operation necessarily has identical runtime exposure, boundary behaviour, or test coverage. The existence of the family must not be confused with every conceivable topology workflow being complete.

---

## 5. Undo / Redo and Snapshot Behaviour

Topology changes that use the existing `MeshStateCommand` path are snapshot-based and participate in the shared history mechanism.

Current tests cover topology state changes and history behaviour, including commit/cancel and undo/redo scenarios for the implemented operations. This provides the required reversibility for research use without introducing a second topology-specific history system.

This is sufficient to treat topology manipulation as observable experimental action rather than an irreversible prototype-only mutation.

Remaining operation-specific edge cases are research/implementation details and should be documented against the relevant experiment rather than generalized into a claim that “Topology is missing.”

---

## 6. Selection → Topology → Mesh Update

The current system separates selection state from topology operation state while allowing topology operations to consume the current mesh/selection and produce an updated mesh state.

The important architectural principle is:

- Selection identifies the current component/context.
- A topology operation acts on that context.
- The resulting mesh state is committed through the existing history/state machinery.
- The renderer then observes the updated mesh state through the established Playground rendering path.

This is already enough infrastructure for research questions in which the artist notices a deformation/topology issue, edits the mesh, and continues observing.

The exact affordance and interaction quality of each operation remains an empirical question; the Host audit should not turn that into a blanket architectural rewrite.

---

## 7. What the Previous V1 Audit Got Right

The 2026-09-13 audit remains useful as historical context. Its central observations were valid at that time:

- `Experiment` and `ExperimentSlot` were sound minimal abstractions.
- The live window and Host were initially disconnected.
- A single active slot was insufficient for the intended multi-family research model.
- Navigation/transform precedence was a real runtime interaction finding rather than a missing Host concept.
- A research Host should not grow into a dependency matrix or observation database.

Those findings should not be discarded; they are simply no longer a description of the complete current implementation.

---

## 8. Obsolete V1 Findings

The following V1 conclusions are now obsolete and must **not** be reused as current repository facts:

### Obsolete: single active Host slot

The application is no longer limited to one tracked family slot. The current Host uses a per-family registry.

### Obsolete: Host machinery unused by the live Playground

The current runtime registers and activates experiment families through the Host machinery. The previous statement that the Host existed only as a tested library while the real Playground bypassed it is no longer an accurate description of the current main branch.

### Obsolete: only Selection / Transform / Presentation families exist

Tweak and Topology are now present in `playground/experiments/` and are wired into the current runtime research surface.

### Obsolete: Topology does not exist / AP-05 is deferred

This is explicitly superseded. Topology experiments and runtime topology operations exist today.

---

## 9. Remaining Current Gaps

The current gaps should be understood as **research/runtime completeness gaps**, not as justification for rebuilding the Host.

### A — Not every experiment family represents a final UX decision

The Host makes variants observable and recordable. It does not decide which interaction is best. `UNDECIDED`, `KEEP`, `ITERATE`, and `REJECT` remain research states.

### B — Individual topology behaviours remain incomplete/open

Some topology behaviours and edge cases remain unresolved or intentionally under research. Examples include boundary-loop continuation, open-loop slide behaviour, even-spacing/clamping, and other operation-specific details documented by the topology experiments/tests.

These should remain localized to the relevant experiment rather than becoming a reason to redesign the Host.

### C — Navigation and transform coexistence remains an interaction finding

The existing transform-key precedence means that holding transform keys can prevent camera orbit/pan gestures during the same interaction. This remains a useful baseline observation and should be treated as a UX research question, not silently “fixed” as part of Host maintenance.

### D — Runtime wiring should remain verified against code

Because the Playground is evolving quickly, future audits should verify actual registration, activation, and runtime paths instead of assuming that a folder or roadmap entry proves live availability.

---

## 10. Implications for EX-A

EX-A asks:

> **Does temporary articulation help the artist detect and respond to problems earlier while modeling?**

The current Host/Playground state supports a stronger experiment than a pure visual inspection task.

If temporary articulation exposes a topology/deformation problem, the artist can potentially:

1. inspect the articulated result,
2. identify the relevant topology/components,
3. modify the topology using the existing Playground operations,
4. observe the result again,
5. undo/redo as needed,
6. and record what actually changed in the modeling decision.

That makes the **actual intervention itself observable evidence**. EX-A should therefore not be constrained to “see and name” if the current runtime already provides the required topology manipulation.

The Blender/DCC calibration remains useful as a low-cost discovery step for articulation feel, pivot behaviour, deformation visibility, and general experiment design. It is **not** a prerequisite for establishing whether the Playground can manipulate topology — that capability already exists in the current repository.

---

## 11. Audit Conclusion

The Experiment Host is no longer in the early single-slot state described by the 2026-09-13 audit.

The current Playground has a functioning multi-family experiment surface covering Selection, Presentation, Transform, Tweak, and Topology. Topology is substantially implemented and can be used for actual mesh manipulation, with existing history/snapshot mechanisms providing reversibility for the relevant operations.

The correct development posture is therefore:

> **Use and audit the current Host and experiments; do not rebuild them based on stale documentation.**

For future work, current code/tests on `main` remain authoritative. Research documents describe questions and observations; they must not be used to infer that an implemented capability is missing simply because an older audit or roadmap predates it.

**Stop condition reached. No implementation performed.**
