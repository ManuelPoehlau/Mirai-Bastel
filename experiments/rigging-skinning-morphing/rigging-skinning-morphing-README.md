# Rigging, Skinning & Morph-Targets Experiment

## Overview

This experiment investigates how skeletal rigging, skinning weights, and morph-targets can coexist cleanly with **topological mesh editing** — a capability historically rare outside specialized tools like the original Mirai.

**Core Question:** Can we edit the topology of a rigged, weighted, morphed mesh without destroying the rig, weights, or morph-target integrity?

**Use Case:** Low-poly character head workflow
- Neck, skull, jaw rigged with 3 bones
- Vertices weighted to bones (skinning)
- Facial deformations via morph-targets (mouth open, jaw drop, etc.)
- Then perform a topology operation (e.g., edge-loop insert in the face)
- Verify: Do weights auto-update? Do morphs stay intact? Does the rig still function?

## Context & Links

### Parent Documentation
- **Project Vision:** [docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md](../../docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md)
  - Living 3D System: Modeling → Deformation → Rigging → Animation
  - This experiment validates a core integration hypothesis

- **Core Hardening Plan:** [docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md](../../docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md)
  - Phase A–E completed; Phase F (Production Freeze)
  - Key finding: ID-management constraints affect skinning design (see Phase C findings)

- **Topology Experiment (Phase 2):** [experiments/mirai_bastel_viewport_V1/TOPOLOGY_EXPERIMENT_PLAN.md](../mirai_bastel_viewport_V1/TOPOLOGY_EXPERIMENT_PLAN.md)
  - Edge-loop selection, insertion, removal already working
  - This experiment builds on that foundation

### System Architecture
- **SOURCE_ARCHITECTURE.md:** How Core.Mesh is structured
- **AD-001 (ID Continuity):** Why Undo/Redo uses state snapshots, not semantic ops
- **Viewport:** Python + OpenGL (not web-based)

## Viewport V1 Integration — Living Mesh Research (current)

Das Experiment hat **keinen eigenen Viewport** und soll auch keinen bekommen.
Stattdessen nutzt es den vorhandenen Viewport V1 (All-Tools-Playground) aus
[`experiments/mirai_bastel_viewport_V1/`](../mirai_bastel_viewport_V1/README.md)
als gemeinsame Darstellungsschicht:

```text
Viewport V1 (All-Tools-Playground)
        ↓
Rigging Experiment Scene  (OBJ Head Basemesh → Mesh)
        ↓
Living Mesh / RigController  (später)
```

Der Viewport sieht dabei **nur eine normale `Scene`/`Mesh`** — er weiß nicht,
dass es ein Rigging-Experiment ist. Kein Viewport-Fork, keine Änderung an
Viewport- oder Core-Dateien.

### Start

```bash
cd experiments/rigging-skinning-morphing
python run_viewport.py
```

Öffnet den All-Tools-Playground mit dem echten Head-Basemesh
(`meshes/head_basemesh.obj`) statt der Würfel-Testszene, inklusive
Start-Report (Vertices/Edges/Faces/Face-Typen/Bounds) auf der Konsole und
Window-Titel „Mirai-Bastel — Living Mesh Research". Alle vorhandenen
Werkzeuge laufen unverändert weiter: Selection (V/E/F), Topology (S/K/C/L/R),
Transform (M, Shift+R, Shift+S, X/Y/Z), Undo/Redo, Display-Modi (O/W).

### Dateien dieser Integration

```text
loaders/obj_loader.py        - OBJ-Parser (v/f, 1-basiert→0-basiert, v/vt/vn-
                               tolerant, KEINE Triangulation, core-/pyglet-frei)
loaders/__init__.py          - Paket-Exporte
viewport_adapter.py          - OBJ → Scene (mirai_bastel_core), Bounds/Face-
                               Stats, Kamera-Framing, Debug-Report (pyglet-frei,
                               headless testbar)
run_viewport.py              - Launcher + minimale Fenster-Unterklasse
                               (Scene-Tausch über den bestehenden
                               TopologyWindow-scene-Parameter, Caption-Titel,
                               Kamera-Framing)
Tests/test_obj_loader.py     - Loader-Unit-Tests
Tests/test_viewport_integration.py - Strukturtest OBJ → Mesh → Scene (headless)
Tests/conftest.py            - pytest-Kontext (Pfad-Bootstrap + Workaround für
                               pytest 9.x mit dem hyphen-behafteten
                               Experiment-Ordnernamen, siehe Datei-Docstring)
```

### Architekturentscheidungen

- **Szene baut auf `mirai_bastel_core`** (dem Core des Viewport-Experiments),
  nicht auf `src.core`: Der Viewport V1 ist an `mirai_bastel_core` gebunden;
  nur so nutzen Szene, Selection, History und Tools garantiert dieselben
  Klassen. Die übrigen Rigging-Module (bone/deformation/rig_controller auf
  `src.core`) bleiben unberührt; ein Angleich ist eine spätere, bewusste
  Entscheidung.
- **Fenster-Adapter über bestehenden Hook:** `TopologyWindow` besitzt bereits
  einen `scene`-Parameter; die Unterklasse in `run_viewport.py` ruft
  `TopologyWindow.__init__(scene=...)` explizit und anschließend
  `_init_all_tools()` auf — exakt der Initialisierungsweg von
  `AllToolsWindow`, nur mit eigener Szene. Falls sich der Playground-Init
  ändert, muss nur dieser Adapter nachgezogen werden.
- **Kamera-Framing statt Mesh-Zentrierung:** Der Head ist nicht um den
  Ursprung zentriert (Bounds X −2.605…2.605, Y 0…4.778, Z −1.648…1.648).
  Der Adapter richtet nur die Kamera auf die Mesh-Bounds aus; die Asset-
  Koordinaten bleiben unangetastet (wichtig für spätere Skin-Weights/Morphs).

### Bekannte Grenzen (bewusst dokumentiert, nicht gefixt)

- Der Viewport baut Geometrie bei jedem Hover-/Drag-Event neu auf
  (`_rebuild_geometry`, O(V×F) Normalen). Bei 326 Vertices merkbar träger als
  die Testwürfel-Szene, aber interaktiv nutzbar. Bei größeren Meshes ist das
  ein Viewport-Thema, kein Rigging-Thema.
- Picking (Vertex/Edge/Face) funktioniert mit der Head-Topologie; eine
  systematische Prüfung aller Tools an der Quad-Topologie (z. B. Edge Loop/
  Ring über nicht-reguläre Bereiche) ist bewusst noch offen.
- `Tests/test_topology_operations.py` (bestehende Datei) nutzt
  `@pytest.fixture(skipif=...)` — eine nie gültige pytest-API, die unter
  pytest 9.1 die Sammlung dieser einen Datei verhindert. Unabhängig von dieser
  Integration; kein Bestandteil dieses Workstands.

## Independence & Parallel Work

This experiment **runs independently** from WP 02 (Cline's work).

- No blocking dependencies
- Evidence feeds forward into WP 02 design
- Both can progress without coordination
- Experiment code is disposable; only validated learnings move to src/

## Current Phase: Research & Architecture Decision

### What We're Doing Now
1. **RESEARCH.md:** Analyze Core's ID management, topology ops, and serialization
2. **DESIGN.md:** Sketch three architectural options (A: Skinning in Core, B: External Mapping, C: Hybrid)
3. **Architecture Decision (AD-XXX):** Choose one, document rationale

### Files in This Experiment
```
experiments/rigging-skinning-morphing/
├── README.md                           ← You are here
├── RESEARCH.md                         ← Ongoing findings from Core analysis
├── DESIGN.md                           ← Architecture option sketches
├── AD-XXX-RIGGING-CORE-INTEGRATION.md  ← TBD: Chosen decision
└── src/                                ← Working prototypes (Phase 2+)
    ├── bone.py
    ├── skinning.py
    ├── morph_targets.py
    └── deformation_viewport.py
```

## Next Steps

### Immediate
- [ ] Read CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md and extract relevant findings
- [ ] Create RESEARCH.md with summary of ID management, topology ops, serialization
- [ ] Write DESIGN.md with three architectural options

### Then
- [ ] Architecture Decision (choose option A/B/C)
- [ ] Begin Phase 2 prototype (minimal bone/skin/morph code)
- [ ] Implement topology-aware integration test

## Principles (from AGENTS.md)

- **Capture first, discuss second, decide third, implement fourth**
- **Implement little, assume much**
- Never silently change Core architecture; document decisions first
- Documentation is part of the engineering system—not disposable chat notes
- Experiment code is pragmatic and disposable; only extract validated architecture to src/

## Related Experiments
- **Topology Experiment Phase 2:** Edge-loop selection, insertion, removal
- **Viewport (Python + OpenGL):** Real-time mesh visualization

---

**Started:** August 2026  
**Status:** Phase 1 – Research & Architecture Design  
**Owner:** Manu (with Cline's WP 02 separate and independent)
