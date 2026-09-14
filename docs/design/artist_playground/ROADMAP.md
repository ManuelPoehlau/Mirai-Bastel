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
WP-AP-02.5 (Viewport Presentation Lab)  ✓ done  (b9b7ea6)
    │
    ▼
WP-AP-03 Phase 0 (Playground Controls)  ✓ done  (aeab079)
    │
    ▼
WP-AP-03 Phase 1 (Single Select)        ✓ done  (8971502)
    │
    ▼
WP-AP-03 Phase 2 (Modifier/Toggle)      ✓ done  (8b38736)  ← current
    │
    ├──▶ WP-AP-03 Phase 3 (Marquee)
    ├──▶ WP-AP-03 Phase 6 (Feedback)
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

**Status:** Phase 0–2 done | **Phase-2-Commit:** `8b38736` (2026-09-11)

**Phase 0 — Playground Controls:** `PlaygroundInputMap` (frei konfigurierbar), 15 Tests
**Phase 1 — Single Select (Replace):** Face-Click → selection, 14 Tests  
**Phase 2 — Modifier/Toggle:** Shift=Add/Ctrl=Remove/Alt=Toggle oder Toggle-only, 22 Tests

**Total:** 51 Tests, 122 Playground-Tests grün, Selection-Baseline funktioniert.

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

**Status:** IN PROGRESS — Multi-Face-Extrude (Region) implementiert (2026-09-14)

### AP-05-Auftakt — Baseline Extrude (Discovery, kein Production-Schritt)

**Implementiert:**
- `playground/topology_tools/extrude.py` — `ExtrudeTool` als `Tool`-Subklasse (Production-Core, nicht V1-Fork)
- `playground/experiments/topology/variant_extrude_baseline.py` — Experiment-Wrapper für den topology-Slot
- `playground/window.py` — topology-Slot registriert; E = activate/begin, LMB-Drag = update, LMB-Release = commit, ESC = cancel
- `playground/tests/test_topology_extrude_baseline.py` — 8 Headless-Baseline-Tests (commit/selection/undo/redo/cancel + Regression begin-remap + Hover-Fallback), alle grün

**Reihenfolge-Hinweis:** Extrude wurde **vor** Phase 3 (Connect Edges) und Phase 4 (Loop Insert) implementiert, nicht danach wie ursprünglich in `TOPOLOGY_EXPERIMENT_PLAN.md` geplant. Grund: Der AP-05-Auftakt ist ein Discovery-Schritt der gezielt Extrude als erste größere Topologie-Interaktion aufgreift, bevor Connect- und Loop-Insert-Semantik final geklärt ist. Die Phase-Nummerierung im Plan bleibt erhalten — die Durchführungsreihenfolge weicht bewusst ab.

### AP-05 — Multi-Face-Extrude (Region) (Discovery, kein Production-Schritt)

**Implementiert (2026-09-14):**
- `ExtrudeTool` auf `begin(face_ids: set[FaceId])` verallgemeinert (echter Refaktor via Boundary-Edge-Regel, kein Parallel-Code)
- `window.py` — 2+-Faces-No-op entfernt; 1+ selektierte Faces → Multi-Face-Extrude; Hover-Fallback bleibt auf 1 Face begrenzt
- 4 neue Multi-Face-Tests (benachbarte Faces/geteilte Edge ohne Wand, nicht-benachbarte Faces/volle Seitenwände, Cancel/Multi-Selection, Undo/Redo) — 12 Tests gesamt, alle grün

**Bewusste Entscheidungen:**
- Normale als gemittelte Region-Normale (normalisierte Summe der Newell-Normalen aller Faces) — erste Version, keine finale Antwort auf die Normal-/Richtungsfrage
- Caps sind 1:1 auf neue Vertex-IDs gemappt, keine Verschmelzung zu größeren Polygonen

**Nächster Schritt:** Artist-Verdict (decision.md für den topology-Slot).

### AP-05 — Connect Edges (Enablement-Port, kein Production-Schritt)

**Implementiert (2026-09-14):**
- `playground/topology_tools/connect_edges.py` — 1:1-Logik-Port aus V1 gegen Production-`src/core`; 3-Phasen-Plan (Analyze → Plan/Dry-Run → Apply); 1 MeshStateCommand pro Operation
- `playground/window.py` — Taste **J**: Edge-Modus + 2+ Edges selektiert → Connect; neue Verbindungskanten werden selektiert; TopologyToolError → HUD-Meldung statt Crash
- `playground/tests/test_topology_connect_edges.py` — 7 Headless-Tests, alle grün

**Nachgezogen (2026-09-14):**
- `src/core/mesh.py` — `add_edge()` als öffentliche Mutation-Primitive (additiv, AD-001/002/003 unberührt)
- `connect_edges.py` — "kind v"-Fall aktiviert: `_FreeConnectStep` + `mesh.add_edge()` für Ketten-Verbindung über gemeinsamen regulären Innen-Vertex ohne Face-Kontext
- `playground/tests/test_topology_connect_edges.py` — 9 Headless-Tests (3 neue: kind-v positiv, kind-v Undo/Redo, Boundary-Vertex-Ablehnung), alle grün

### AP-05 — Loop/Ring Select (Enablement-Port, kein Production-Schritt)

**Implementiert (2026-09-14):**
- `playground/topology_tools/loop_ring.py` — 1:1-Logik-Port aus V1 (`loop_ring.py`) gegen Production-`src/core`; reine Query, keine Mutation; `edge_loop()`, `edge_ring()`, `Traversal`, `LoopRingError`
- `playground/window.py` — **Shift+L**: Edge-Modus + 1+ Edges → Loop Select; **Shift+R**: Edge-Modus + 1+ Edges → Ring Select; HUD zeigt Anzahl + offen/geschlossen
- `playground/tests/test_topology_loop_ring.py` — 6 Headless-Tests (Ring auf Cube geschlossen, Loop auf Cube stoppt, Loop durch Valenz-4-Vertex, offener Ring, LoopRingError), alle grün

**Bewusst ausgeklammert:** Boundary-Loop-Fortsetzung (offener Rand), Loop Insert als Folgeop.

### AP-05 — Loop Insert (Enablement-Port, kein Production-Schritt)

**Implementiert (2026-09-14):**
- `playground/topology_tools/loop_insert.py` — `loop_insert(scene, start_edge)`: erkennt Ring via `edge_ring()`, delegiert an `connect_selected_edges()`; 1 MeshStateCommand (via Connect Edges), `LoopInsertError` für alle Fehlerfälle
- `playground/window.py` — Taste **I**: Edge-Modus + 1+ Edges selektiert → Loop Insert; neue Kanten werden selektiert; Fehler → HUD-Meldung
- `playground/tests/test_topology_loop_insert.py` — 6 Headless-Tests (Topologie wächst, 1 History-Eintrag, Undo/Redo, ungültige Edge, freie Edge, Determinismus), alle grün

**Bewusst ausgeklammert:** Interaktive Positionierung (Loop Slide), mehrfache gleichzeitige Inserts.

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
