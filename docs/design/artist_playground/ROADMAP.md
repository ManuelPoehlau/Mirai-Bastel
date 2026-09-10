# Artist Playground — Roadmap

**Status:** Planning (pre-implementation)
**Date:** 2026-09-10
**Derived from:** [Architecture Map](ARCHITECTURE_MAP.md)

---

## Development Model

The Artist Playground follows a research-first model, not a feature-delivery model.

```
Question
    ↓
Playground
    ↓
Variant A / B / C
    ↓
Manuel plays with it
    ↓
Artist Verdict
    ↓
Candidate
    ↓
Production
```

**Production is not where we discover what is good. Production is where we cleanly implement what has already proven itself.**

This roadmap is therefore not a feature checklist. It is a sequence of research phases, each enabling the next. Later phases may be redefined based on what earlier phases reveal.

---

## Dependency Order

```
WP-AP-01 (Foundation)                   ✓ done
    │
    ▼
WP-AP-02 (Experiment Host)              ✓ done
    │
    ▼
WP-AP-02.5 (Viewport Presentation Lab)  ✓ done  baseline: b9b7ea6
    │
    ▼
WP-AP-03 Phase 0 (Playground Controls)  ← next
    │
    ▼
WP-AP-03 (Selection Lab)
    │
    ├──▶ WP-AP-04 (Tool Variant Lab)
    │
    └──▶ WP-AP-05 (Topology Lab)
```

WP-AP-03, -04, -05 can run in parallel — they share only the infrastructure from WP-AP-01/02.

---

## WP-AP-02.5 — Viewport Presentation Lab ✓

**Status:** Done | **Baseline-Commit:** `b9b7ea6` (2026-09-11)

Multi-Pass-Rendering im Playground: Smooth Shaded, Flat Shaded, Wireframe, Vertices (GL_POINTS),
Edges (GL_LINES) und alle Kombinationen davon. Sechs `PresentationExperiment`-Varianten.
`DisplayState` aus Production direkt wiederverwendet. VBO-Daten-Builder headless testbar.

27 neue Tests. Darstellungsbasis für AP-03 (Selection Feedback) bereit.

Detailed plan: [AP-03_PLAN.md](AP-03_PLAN.md)

---

## WP-AP-01 — Artist Playground Foundation

**Goal:** The Playground runs. The artist can see a mesh, operate the camera, and start a first experiment.

### What gets built

| Component | Type | Source |
|-----------|------|--------|
| `PlaygroundWindow` — lightweight pyglet GL host, no fixed scene | 🔴 NEW | Integration Lab `lab_viewport.py` as reference |
| `PlaygroundApp` — minimal orchestrator with Experiment Slot | 🔴 NEW | `Application` (WRAP, not changed) |
| `PlaygroundHUD` — standalone HUD class, configurable | 🟡 ADAPT | extracted from `lab_viewport.py` |
| `PlaygroundRenderer` — adapter onto `src/viewport/` | 🔵 WRAP | Production Viewport untouched |
| Camera, Picking, Input, Commands connected | 🟢 REUSE | ready now |
| Cube + Head Basemesh loadable | 🟢 REUSE | OBJ loader already present |
| Playground test harness (base) | 🔴 NEW | Lab test pattern as template |

### Result after WP-AP-01

```
python playground/run.py
→ Window opens
→ Cube or Head visible
→ Orbit / Zoom / Pan works
→ HUD shows: camera state, active experiment, mesh info
→ Production tests: green
```

### Explicitly NOT in WP-AP-01

- No Select Tool
- No experiment variants
- No decision system
- No new modeling tools

---

## WP-AP-02 — Experiment Host

**Goal:** Anti-chaos system. We can define variants, test them, and record a decision.

### Minimal scope (deliberately)

```python
class Experiment:
    id: str
    name: str
    variant: str
    def activate(): ...
    def deactivate(): ...
    def update(): ...
    def draw(): ...
```

Switching variant = one line change. Decision = fill in `decision.md`. No framework, no registry overhead, no persistence engine.

### Decision record format

```markdown
# <Experiment Name> — <Variant>

Decision: KEEP / ITERATE / REJECT

What felt better:
- ...

What felt worse:
- ...

Artist verdict:
- ...
```

### File structure

```
playground/
  experiments/
    select_box/
      variant_a.py
      variant_b.py
      decision.md
```

### Result after WP-AP-02

- New variant = new file, no refactoring
- Decision documented in `decision.md`
- Active experiment visible in HUD

---

## WP-AP-03 — Selection Lab

**Detailed plan:** [AP-03_PLAN.md](AP-03_PLAN.md)

**Goal:** Answer the most important open UX question: *How should selection feel?*

This is the first major research work package. It comes before Tool Variants because Selection is the foundation for almost everything else in the editor.

### Open research questions

- What feels right when clicking a vertex / face / edge?
- How should selection be visualized?
- What does Shift do?
- How does Box-Select behave?
- Does Lasso feel right?
- Is Paint Select useful at all?
- What happens on Drag vs. Click?
- How fast does feedback need to arrive?
- How important is "selection persists across operations"?
- How should Selection interact with Tools?

### Missing piece (from Architecture Map)

The connection between Picking hit → `core.selection.set_selection()` does not yet exist. This is the core build in WP-AP-03.

### Experiment variants

| Variant | Experiment |
|---------|-----------|
| Click-Select (single) | Baseline |
| Toggle-Select (Shift) | Variant A |
| Box-Select | Variant B |
| Lasso-Select | Variant C |
| Paint-Select | Variant D |

Each variant is its own Experiment Slot. Artist plays with each. Decision record captures the verdict.

### Dependencies

- WP-AP-01 (Playground runs)
- WP-AP-02 (Experiment Slot system)

---

## WP-AP-04 — Tool Variant Lab

**Goal:** Research Move / Transform variants not yet present in Production.

**Status: Open — content defined after WP-AP-03 Artist Verdict.**

The current hypotheses (axis constraint, soft selection, incremental vs. absolute) may not turn out to be the right research questions. After WP-AP-03, the actual open questions may shift — for example:

> "Our biggest problem is not Move itself, but how Selection and Transform flow together."

WP-AP-04 will be scoped based on what WP-AP-03 reveals.

### Dependencies

- WP-AP-01
- WP-AP-02
- WP-AP-03 (Artist Verdict informs scope)

---

## WP-AP-05 — Topology Lab

**Goal:** Research Topology Phase 4 (Loop Insert) and Phase 5 (Extrude) in the Playground before Production integration.

**Basis:**
- V1 `topology_tools.py` as reference code
- Topology specs from `experiments/topology/`
- Production `operations/topology.py` (MeshStateCommand)

**Mode:** Playground-first → Candidate → Production.

**Status:** Deferred until WP-AP-04 completes.

---

## Invariants for All Phases

```
🏭 src/core/     →  never change
🏭 src/viewport/ →  never change directly (WRAP only)
🏭 tests/        →  always green
```

---

## Relationship to the Main Project Roadmap

The Artist Playground is a research initiative that feeds the main production roadmap (`docs/architecture/ROADMAP.md`). Candidates that prove themselves in the Playground become inputs to WP-02 (Interaction & Tool Framework), the Modeling Track, and future work packages.

The Playground does not replace the production roadmap. It is the mechanism by which future production work packages get validated UX foundations rather than assumed ones.
