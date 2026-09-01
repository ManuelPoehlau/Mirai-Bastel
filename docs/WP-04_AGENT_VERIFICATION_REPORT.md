# WP-04 — Agent Verification & Preparation Report

**Date:** 2026-09-01 (Verification Session, branch `wp/04-production-foundation`)
**Role:** Independent Verification / Test Engineer / Preparation Agent
**Scope:** Repository-Analyse → bestehende Tests ausführen → mechanische Lücken schließen → Claude-Vorbereitung
**Status:** Vorbereitung abgeschlossen; keine Produktions-Implementierung, keine `src/core`-Änderung, keine Git-Operation durchgeführt

> Dieses Dokument ist der Abschlussbericht der Agent-Phase für WP-04. Es ergänzt
> [WP-04_PRODUCTION_FOUNDATION_DISCOVERY_REPORT.md](WP-04_PRODUCTION_FOUNDATION_DISCOVERY_REPORT.md)
> (Analyse/Konzept) um die Verifikations-Ergebnisse, das Test-Inventar und die
> Aufgabenteilung Agent/Claude/Manuel. Discovery- und Reassessment-Dokumente
> bleiben die Quelle für die Architektur-Entscheidungen.

---

## A. Repository Status

| Bereich | Befund |
|---|---|
| Branch | `wp/04-production-foundation` ✓, Arbeitsverzeichnis sauber |
| `src/core` | Core V1, eingefroren; Produktions-Suite **29/29 + Architekturverträge PASS** |
| `experiments/mirai_bastel_core_V1` | Fork inkl. WP-03 Transform-Foundation (`operations/transform.py`); Architekturverträge PASS |
| `experiments/mirai_bastel_viewport_V1` | WP-01A/02/03 abgeschlossen; **134/134 Tests PASS (pytest)** |
| `src/mirai/` | **Existiert nicht** — Gate 3 (Application Foundation) ist unbegonnen |
| Entry Point | Fehlt (kein `main.py`, kein Application-Lifecycle) — bekanntes Gate-3-Deliverable |
| Build/Tooling | Kein `pyproject.toml`/`setup.py`; Python 3.14/3.12; `pytest 9.1.1`, `pyglet 2.1.16` (Experiment-only); Tests via `unittest`/`pytest` bzw. `python -m tests.run_core_suite` |

### Nebenbefunde (nicht behoben, dokumentiert)

1. **`src/core/move.py` ist ein verwaistes Duplikat** von `src/core/operations/move.py`
   (identischer Inhalt). Nichts importiert `core.move` — Rest mit Divergenzrisiko.
2. **`tests/` enthält tote Hilfskopien:** `tests/history.py`, `tests/mesh.py`,
   `tests/operations_init.py` — nirgends importiert (Tests laufen gegen `src/core`).
3. **`tests/mnt/user-data/outputs/phase_e/`** ist ein Artefakt-Baum aus einer
   Sandbox-Umgebung (kopierte Runner), kein echter Test-Code.
4. **Testzahl-Dokumentation inkonsistent:** WP-02/WP-03-Berichte nennen „88/88“
   für den Viewport — das ist nur die `unittest`-Teilmenge; mit `pytest` sind es
   **134**. Die 46 zusätzlichen Tests (pytest-Stil) existieren und laufen grün.

---

## B. WP-01/02/03 Dependency Map

```text
src/core  (FROZEN V1, production)
   ▲  keine Abhängigkeit nach oben; nur stdlib-Importe
   │
WP-01A  Input/Binding/Command/Display (viewport/input_binding.py,
        commands.py, default_bindings.py, display_state.py, camera.py, picking.py)
   ▲  Tests: test_input_binding (8), test_display_state (5), test_camera_picking (11)
   │
WP-02   Tool Framework (viewport/tool.py: Tool + ToolManager) + MoveTool
        (move_tool.py: resolve_selection_vertices, tool_for_command)
   ▲  Tests: test_tool_lifecycle (7), test_move_tool (7), test_tool_integration (16),
        test_tool_routing (4)
   │
WP-03   Transform Foundation (FORK: mirai_bastel_core/operations/transform.py:
        VertexTransformOperation/RotateOperation/ScaleOperation + transform_tool.py:
        TransformTool/RotateTool/ScaleTool/selection_pivot)
   ▲  Tests: test_transform_operations (18), test_transform_tools (22),
        test_transform_integration (14), test_tool_routing (+2)
   │
WP-04   src/mirai (GATE 3) — noch nicht begonnen; konsumiert WP-01/02/03 + Core
```

Kritische Verifikationen:
- **Die `unittest`-Loader-Suite (88) ist nicht die Gesamtzahl**: die vollständige
  Viewport-Suite hat 134 Tests (pytest). Beide laufen grün.
- Fork-Architekturverträge (`mirai_bastel_core_V1/tests/test_core.py`) laufen
  separat und ggrün gegen den Fork.
- Repo-Tests (`tests/`) laufen ausschließlich gegen `src/core` (via `tests/_bootstrap`).
---

## C. WP-03 Transform Findings

**Getestet/verifiziert (Fork + Tools, 134er-Suite):**

| Aspekt | Befund |
|---|---|
| Rotate-Mathematik | Rodrigues um fixen Pivot; Weltachse/Default=Blickachse; inkrementelle Winkel-Addn |
| Scale-Mathematik | uniform (float) + per-Achse (Tupel); Faktor-Multiplikation inkrementell |
| Pivot-Semantik | fix seit `begin()`; Default = Selection-Center (Zentroid; explizit über `params["pivot"]` |
| Commit | genau 1 History-Eintrag, exakte Start-/Endpositions-Commands (kein Delta) |
| Cancel | exakte Wiederherstellung, keine History |
| No-op | `commit()` → `None`, kein Eintrag |
| Chunking | kumulierte Pixel-Distanz → Zielschritt ⇒ event-chunking-unabhängig |
| Min-Clamp (Scale) | kein Spiegel-/Degenerations-Pfad durch die Geste |
| Selection | `_VertexSelectionView`/`_MoveSelectionView` als Core-Ansicht; `resolve_selection_vertices` V/E/F→Vertex |

**Grenze Core↔Production (Auftragspunkt 2):**

Die Architekturentscheidung „Move/Rotate/Scale + geometrische Constraint-Semantik
in den Core; Benutzerinteraktion nicht“ ist im Code bereits sauber reflektiert:

- Core-Ebene (Fork, promotionskandidat): `RotateOperation.update(axis=…, angle=…)`,
  `ScaleOperation.update(factor=float|tripel)` — rein geometrisch, kein UI-Bezug. 
- Tool-Ebene: `RotateTool`/`ScaleTool` rechnen Pixel→Schritt, holen die
  Kamera-Blickachse, mappen Geste→Faktor/Winkel. `INPUT_COMMAND_TOOL_CONTRACT.md`
  §5 (Operationen ohne UI/Input-Abhängigkeit) wird eingehalten] 

**Kein Widerspruch gefunden.** Einzige Inkonsistenz: `MoveOperation` lebt in
`src/core`, `Rotate/Scale` nur im Fork — die Promotions-Entscheidung (Q1) ist
noch nicht formal getroffen/dokumentiert (siehe I + K).

---

## D. Constraint Findings

| Semantik | Im Core/Fork | Im Tool | Interaktiv/UI | Tests |
|---|---|---|---|---|
| Rotate: Weltachse X/Y/Z | ✓ `axis=` (Rodrigues) | ✓ `begin(axis=…)` | ✗ | `test_transform_tools` |
| Rotate: beliebige Achse | ✓ | ✓ | ✗ | ✓ |
| Scale: uniform / X/Y/Z-Maske | ✓ `factor=` Tripel / Maske | ✓ `begin(axes=…)` | ✗ | ✓ (`test_axis_constraint_mask`) |
| Move: Achsen-Constraint | ✗ | ✗ (unconstrained) | ✗ | ✗ |
| Ebenen-Constraints XY/YZ/XZ | ✗ | ✗ | ✗ | Nur Hotkey-Mapping (`test_constraints`,3) |
| `constraint_from_key()` / `Constraint`-Enum | — | — | — | Nur Mapping-Ebene |

Kernbefund: `viewport/constraints.py` ist ein **unverdrahtetes Mapping-Modul**
(Enum NONE/X/Y/Z/XY/YZ/XZ + Key→Constraint}, nirgends von einem Tool oder dem
Window genutzt (kein Command, kein Binding, kein Dispatch. Als „WP-04: Tool-
Parameter statt interaktiver Hotkeys“ ist das eine bewusste, dokumentierte
Grenze (Discovery-Report §8, Viewport-README „Bewusst außerhalb“)— aber für
den Test-Inventar-Zweck heißt das:**Achsen-/Ebenen-Echtverhalten für Move/Rotate/
Scale im Produktionspfad existiert noch nicht** (Tests dafür sind Spezifikation,
keine Implementierung — siehe F).
---

## E. Existing Test Coverage (Stand nach Agent-Ergänzung, Abschnitt G)

### Viewport-Experiment (`experiments/mirai_bastel_viewport_V1/tests`, pytest)

| Datei | # | Stil | Deckt |
|---|---|---|---|
| test_camera_picking | 11 | pytest | Kamera/Projektion/Orbit/Pan/Zoom/Picking, screen_delta_to_world |
| test_connect_edges | |12 | pytest | Topology-Lab connect, atomare Fehlerfälle, History-Snapshot |
| test_constraints | 3 | pytest | Hotkey→Constraint-Mapping (X/Y/Z/XY/YZ/XZ/NONE) |
| test_display_state |5 | pytest | Display-Modi, Wireframe-Overlay, Zyklus, Validierung |
| test_input_binding |8 | pytest | Default-Bindings, Modifier, Kontext, keymap.json;„keine Hardcoding-in-Windows“ |
| test_loop_ring |7 | pytest | Edge-Loop/Ring-Erkennung (Quads/Boundary/Röhre) |
| test_move_tool |7 | unittest | MoveTool×MoveOperation: Operationstyp, Updates, Commit=1 Eintrag, Cancel exakt, Undo/Redo |
| test_tool_integration |16 | unittest | M→MoveTool→LMB/Drag/Release/Esc (headless Window-Pfad); Tweak-Move; Selection-Resolver |
| test_tool_lifecycle |7 | unittest | IDLE/ACTIVE/INTERACTING-State-Machine, Guards, kein stale State |
| test_tool_routing |4 | unittest | Command.Move/Rotate/Scale→Tool; Non-Tool-Commands→None |
| test_transform_integration |14 | unittest | R/S-Aktivierung, modale Rotation/Scale-Interaktion, Cancel, Kontext-Bindings, WP-02-Regression |
| test_transform_operations |18 | unittest | Rotate/Scale-Mathematik, Pivot fix/Default, inkrementell, No-op, Commit/Cancel/Undo/Redo, per-Achse |
| test_transform_tools |22 | unittest | RotateTool/ScaleTool: Lifecycle, Gesten, Achsen(für Rotate), Masken(für Scale), Chunking, Min-Clamp, History-Grenzen |
| **Summe** |**134** | | **88 unittest + 46 pytest-Stil** |

### Produktions-Core (`tests/`, gegen `src/core`)

| Modul | # | Deckt |
|---|---|---|
| test_core.py |11 (Funktionen) | Architekturverträge AD-001/002/003, Selection∉History, Serialisierung |
| test_mesh_invariants |7 | Struktur-Invarianten, Boundary, gültige IDs (Phase A) |
| test_topology_mutations |9 | split/collapse/connect: ID-Kontinuität, Adjazenz, Fehlerfälle (Phase B,C) |
| test_identity_continuity |6 | vollständige Vorher/Nachher-ID-Mengen-Diffs (Phase C) |
| test_topology_history |7 | undo/redo exakt inkl. IDs/Beziehungen, Mehrfachsequenzen (Phase D) |
| test_scene_serialization |8 | Dict-/JSON-Roundtrip, Allocator, Kollisionen, Versionsprüfung（Phase E, separat） |
| test_history_contract (NEU) | |10 | HistoryStack-Vertrag: No-op-undo/redo, Redo-Zweig-Verwerfen, LIFO, can_undo/redo |
| test_operation_lifecycle (NEU) | |15 | Operation-State-Machine-Guards, History-Grenzen, No-op/Boundary, Wiederverwendbarkeit |
| **Summe (unittest)** |**62** | | (+25 durch Agent-Ergänzung) |

Standard-Runner `python -m tests.run_core_suite`: weiterhin 29/29 + Verträge PASS
(unverändert; die neuen Module sind bewusst zusätzliche, separat ausführbare
Regressionstests nach dem Muster der Phase-E-Suite).
### Feature-Inventar (Auftragspunkt 3)

| Feature | Existing Test | Coverage | Missing Test | Risk |
|---|---|---|---|---|
| **Move** free | test_move_tool (7), test_core AD-003, test_tool_integration | ✓ | — | LOW |
| Move X/Y/Z | — | ✗ | Spec: „Move axis constraint (Production)“ — Feature existiert nicht | MEDIUM (UX-Erwartung) |
| Move Commit/Cancel/Undo/Redo | test_move_tool, test_core, ops-lifecycle (NEU) | ✓ | — | LOW |
| **Rotate** free | test_transform_operations (10 Rotate-), tools (12), integration (4) | ✓ | — | LOW |
| Rotate X/Y/Z | ✓ Achsen-Override (3 Tests: world axis, case, invalid) | ✓ | Repo-Level-Rotate (nach Promotion) | LOW |
| Rotate Commit/Cancel/Undo/Redo | ✓ (operations/tools/integration) + ops-lifecycle (NEU) | ✓ | — | LOW |
| **Scale** uniform | ✓ (operations 8 Scale-, tools 8, integration 2) | ✓ | — | LOW |
| Scale X/Y/Z | ✓ Maske (test_axis_constraint_mask), per-Achse-Tripel | ✓ | Repo-Level-Scale (nach Promotion) | LOW |
| Scale Commit/Cancel/Undo/Redo | ✓ + ops-lifecycle (NEU) | ✓ | — | LOW |
| **Constraints** X/Y/Z | Mapping (test_constraints,3) | nur Mapping | Echtverhalten (Move fehlt; Rotate/Scale nur als begin-Parameter; interactive Hotkeys fehlen) | MEDIUM |
| XY/YZ/XZ (Ebenen) | Mapping (test_constraints,3) | nur Mapping | Echtverhalten fehlt (nur Enum/Mapping) | MEDIUM |
| weitere Semantik (Snap, Gizmo…) | — | ✗ | Out of Scope (WP-04) | LOW |
| **Tool Lifecycle** activate/begin/update/commit/cancel | test_tool_lifecycle (7), test_tool_integration (16), transform tools | ✓ | Repo-Level nach Extraktion (src/mirai/interaction/tool.py) | LOW |
| Operation Lifecycle (Core-Vertrag) | test_core + test_operation_lifecycle (NEU, 15) | ✓ | — | LOW |
| History-Vertrag (Core) | test_topology_history + test_history_contract (NEU, 10) | ✓ | — | LOW |

---

## F. Missing Test Coverage (dokumentiert als Test Specifications)

Nur Tests für **tatsächlich vorhandene** Architektur dürfen als Implementierung
ergänzt werden. Folgende Lücken sind deshalb dokumentiert, nicht implementiert:

| # | Test-Spec | Nötige Architektur/Entscheidung | Prio |
|---|---|---|---|
| 1 | Move mit Achsen-Constraint (X/Y/Z), Ebenen (XY/YZ/XZ) | MoveTool-Constraint-Unterstützung + Produktions-Tool (Gate 4+/UX-Entscheidung) | H |
| 2 | Rotate/Scale mit interaktiven Hotkey-Constraints (während der Interaktion) | UX-Entscheidung + Binding/Command + Tool-Wiring (constraints.py verdrahten) | M |
| 3 | Repo-Level Rotate/Scale-Operationen (gegen `src/core`) | Q1-Promotion nach src/core (Gate 3, dokumentierte Core-Erweiterung) | H |
| 4 | Produktions-Tool-Suite (src/mirai/interaction/tools/*.py) | Gate 3-Extraktion (tool.py, move/rotate/scale.py、input.py, commands.py, bindings.py, constraints.py) | H |
| 5 | Production ToolManager / Command-Dispatch / Application-Lifecycle | Gate 3 (application.py, window.py, render.py-Extraktion aus app.py) | H |
|  ܫ6 | keymap.json-Schemavalidierung | beschlossener Scope (Discovery-Report Risiko „LOW“)→ kann mechanisch in Gate 3 | M |
|  ܫ7 | Repo-Level Selection-Resolver (V/E/F→Vertex) | Extraktion von `resolve_selection_vertices()` nach Produktion (Gate 4) | M |
|  ܫ8 | Move-Operation No-op-undo/redo-Exaktheit via Tool (mehrfach Commit/Undo/Redo-Sequenzen) | bereits teilweise; vollständige Sequenz-Matrix in Gate-8-Validierung | L |
---

## G. Tests, die der Agent bereits ergänzt hat

Neu, mechanisch aus vorhandener Architektur ableitbar (kein neues Feature, keine
Architektur erfunden`src/core` unverändert):

| Datei | Umfang | Belegt |
|---|---|---|
| `tests/test_history_contract.py` (NEU,10 Tests) | No-op-undo/redo auf leerem Stack, Redo-Zweig-Verwerfen bei push), LIFO-Reihenfolge, can_undo/can_redo-Übergänge, `len()`=nur Undo, `description`-Erhalt, Protocol-Compliance | history.py-Vertrag („Ein neuer Eintrag verwirft den Redo-Zweig“) — vorher nirgends direkt getestet |
| `tests/test_operation_lifecycle.py` (NEU,15 Tests) | Doppel-begin/commit/cancel→OperationStateError, update vor/nach begin/commit/cancel, History-Grenzen (update/cancel nie History, nur commit), No-op-commit→None, Zero-Delta→None, leere Selection als No-op, Wiederverwendbarkeit nach commit/cancel | operation.py-Zustands-Guards(AD-003)— explizite Guard-Tests fehlten ( test_core prüft nur „is_active“, kein Raise |

### Verifikationsläufe (alle grün

```
python -m tests.run_core_suite                    → 29 unittest + Verträge: PASS
python -m unittest tests.test_history_contract        → 10/10 OK
python -m unittest tests.test_operation_lifecycle      → 15/15 OK
python -m unittest discover -s tests -p test_*.py    → 62 tests OK
python -m pytest experiments/mirai_bastel_viewport_V1/tests →134 passed(pytest)
python -m pytest tests                                    → 73 passed (mit neuen Modulen)
```

Kein Test wurde „weggefixt“: ein einziger selbstgeschriebener Test hatte einen
Logikfehler in der Erwartung („redo-Zweig verworfen“ heißt nicht
„can_redo()==False nach vollem Undo“») und wurde im Test korrigiert—der Core war
 korrekt.

---

## H. Production Boundary Review

| Prüfpunkt | Befund |
|---|---|
| Production-Abhängigkeit von `experiments/` | ✗ Keine. Repo-Tests importieren nur `src/core` (`tests/_bootstrap`.; Experimente importieren ihren Fork via `sys.path`-Hacks nur experiment-lokal. |
| Production-Abhängigkeit von Experiment-Entry-Points (run.py等等) | ✗ Keine. `src/` hat keine Entry Points (fehlt noch, Gate 3). experiment Entry Points sind Harness-Lokal. |
| Core→Production-Abhängigkeiten | ✗ Keine. `src/core` importiert ausschließlich stdlib——die Operation/Mesh/History-Verträge sind UI-frei. |
| Core→UI/Input-Abhängigkeiten | ✗ Keine (vertragskonform, INPUT_COMMAND_TOOL_CONTRACT §5. |
| zyklische Abhängigkeiten | ✗ Keine (DAG Core←Viewport-Experimente. |
| unnötige Kopplungen | ⚠ app.py monolithic(582 Zeilen, pyglet-basiert) — bekannt, Gate-3-Extraktion vorgesehen. `constraints.py` unverdrahtet(keine Kopplung, aber auch kein Nutzen. |
| Zielbild | `Production Application → Viewport/Interaction/Tools → Operations → src/core` — strukturell durch die Experiment-Schicht validiert;in `src/` noch nicht existent(Gate 3). |

Empfehlung(dokumentiert, nicht durchgeführt):`src/core/move.py` und die toten
`tests/`-Kopien(`history.py`,`mesh.py`,`operations_init.py`) sowie `tests/mnt/` sind
Cleanup-Kandidaten(keine Funktionswirkung; vor dem Merge in `main` entfernen. → Manuel entscheidet.
---

## I. Core-Reassessment (Freeze-Review, Auftragspunkt 8)

Bewertung der vier Kernfragen am tatsächlichen Code:

| Frage | Befund |
|---|---|
| Passt `MoveOperation` sauber ins Modell? | ✓ Ja. Sie ist die Referenz-Implementierung des AD-003-Vertrags in `src/core`; inkrementelle update-Semantik, Commit=1 History-Eintrag, Cancel=Restore, Soft-Selection-Platzhalter. |
| Passt `RotateOperation`/`ScaleOperation` sauber rein? | ✓ Ja. Sie erben `Operation` über die gemeinsame `VertexTransformOperation`-Basis des Forks und nutzen exakt denselben Vertrag(Snapshot/inkrementell/Commit/Cancel/Start-End-Command. Die Geometrie(Rodrigues, per-Achse-Faktoren) ist Core-tauglich und UI-frei. |
| Passt die Achsen-Constraint-Semantik rein? | ✓ Als **Operations-Parameter** (`axis=`, `factor=`-Tripel/Maske)— das ist Core-Semantik.Interaktive Hotkeys sind bewusst Tool/UI-Verantwortlichkeit(und fehlen noch. |
| Sinnvolle Core-Erweiterung vs. unnötiger Refactor? | **Erweiterung, kein Refactor.** Promotion nach `src/core/operations/transform.py` wäre „Pattern-filling“(Move+Topologie als Präzedenzfälle(, keine neue Abstraktion, kein Umbau bestehender Verträge. Ein Core-V2-Umbau ist ausdrücklich nicht nötig (Option D der Reassessment-Doku abgelehnt. |

**Empfehlung:** Reassessment-Option **C** („Promote + dokumentieren“) bestätigt. Der einzige
offene Schritt ist die formale Q1-Entscheidung + Freeze-Doku-Amendment(K, Manuel.



---

## J. Risiken

| # | Risiko | Schwere | Mitigation/Status |
|---|---|---|---|
| 1 | Q1 (Transform-Ops-Promotion) noch nicht entschieden; blockiert die Gate-3-Reihenfolge( Dateipfade in Gate-3-Planung) | H | Manuel-Entscheidung + Doku (architektur/DECISION_Q1_TRANSFORM_OPS.md) vor Gate 3 |
|  ܫ2 | „88/88“-Zahl in alte Berichte ist die `unittest`-Teilmenge; real 134 (pytest) | L | Dieses Dokument korrigiert; künftig einheitlich „134 (pytest)“ nutzen |
|  ܫ3 | `src/core/move.py`+ tote Tests-Kopien: Divergenz-/Verwechslungsrisiko | L | Cleanup vor Merge (Manuel-Entscheidung) |
|  ܫ4 | `constraints.py` unverdrahtet— UX-Erwartung „X/Y/Z funktioniert“ könnte enttäuschen | M | In README/diesem Report explizit als Out-of-Scope kommunizieren; Gate-4/6 UX-Entscheidung |
|  ܫ5 | app.py monolithic — kann nicht window-frei getestet werden | M (bekannt) | Gate 3: Extraktion in Application/Window/Render(Claude-Kernaufgabe) |
|  ܫ6 | Kein Produktions-Entry-Point— App nicht startbar | H (bekannt) | Gate 3 Deliverable(application + main.py) |
|  ܫ7 | Test-Infrastruktur split(unittest vs. pytest; zwei Runner) | L | Werkzeug-Absprache: `unittest discover` für Core-tests, `pytest` für Experimente; ggf. eine `run_all`-Klammer in Gate 8 |
|  ܫ8 | `tests/mnt/`-Artefakt-Baum aus Sandbox |  L | Cleanup(Manuel( |
---

## K. Claude-Aufgaben (nur wo deutlicher Mehrwert gegenüber dem Agenten)

| # | Aufgabe | Warum Claude | Ergebnis/Kriterium |
|---|---|---|---|
| 1 | **Gate 3: `src/mirai/`-Produktionsstruktur entwerfen + umsetzen** — Extraktion des monolithischen `app.py` (582 Zeilen) in `Application` (window-frei, `interaction/`, `viewport/render.py`, `viewport/window.py`) | Echte Architektur-Entscheidungen: Verantwortungsgrenzen, Lifecycle, Dispatch-Kohärenz, pyglet-Adapter-Design; das Experiment-Konzept muss in Produktionsform **abgeleitet, nicht kopiert** werden | `src/mirai/`-Struktur gemäß Gate-3-Plan; window-freie Tests; keine Regression am Core |
| 2 | **Produktions-Transform-Tools (rotate.py/scale.py) + Tool→Operation→History-Wiring inkl. Selection-Resolver** | Braucht die Gate-3/4-Grenzen (wo lebt resolve_selection_vertices? Tool-Kontext?) und konsistente Integration aller drei Tools | Rotate/Scale-Tools importieren Core-Ops (wie MoveTool), Tests grün |
|  ܫ3 | **Q1-Folgenschritte (falls promotiert):** transform.py→src/core, Exporte, Freeze-Amendment, Test-Migration (Repo-Level) | Kopier+Exporte sind mechanisch; die Freeze-Erzählung „kontrollierte Erweiterung statt Erosion“ will sorgfältige Architektur-Formulierung | Core-Suite + neue Repo-Transform-Tests grün |
|  ܫ4 | **Command-Dispatch/ToolManager integration im Produktions-Application-Lifecycle** (inkl. Undo/Redo-Routing, Kontext-Bindings) | Überlappt mit #1/3; erfordert kohärenten Gesamtentwurf statt Einzelmodule | Keybindings-Routing gemäß Q4-Option A; Tests |
| |5 | **Gate-9/11 Architektur-Review** des Produktions-Stands | Zweite unabhängige Architektur-Prüfung von jemandem, der nicht implementiert hat | Review-Doku, GO/NO-GO-Vorbereitung |

## L. Agent-Aufgaben(der Agent kann erledigen / hat erledigt)

| # | Aufgabe | Status |
|---|---|---|
| 1 | Repository-Analyse + Baseline-Testläufe aller Suiten | ✓ DONE (dieser Report |
|  ܫ2 | Mechanische Core-Contract-Tests(History, Operation-Lifecycle) | ✓ DONE (+25 Tests, Abschnitt G |
|  ܫ3 | Test-Inventar + Test-Strategie (A/B/C-Ebenen) dokumentieren | ✓ DONE (siehe E/F + unten „Teststrategie für WP-04“ |
|  ܫ4 | Produktions-Tests der extrahierten Module 1:1 aus Experimenten übernehmen/migrieren(wenn Gate 3/4 die Module legen) | bereit; mechanisch, sobald Dateipfade existieren |
| |5 | keymap.json-Schema-Validierungstests (sobald Scope bestätigt) | vorbereitet (Spec #6 in F) |
| |6 | Test-Specs für fehlende Features pflegen (Abschnitt F) | ✓ DONE |
| |7 | Coverage-Messung (coverage.py) für Gate-8-Validierung | bereit nach Gate 3 |
| |8 | Cleanup-Kandidaten bewerten aber **nicht** selbst entfernen (src/core/move.py usw.) | dokumentiert (A/H/J; Manuel entscheidet) |

## M. Manuel-Aufgaben (UX / Akzeptanz / GO-NO-GO)

| # | Entscheidung | Termin |
|---|---|---|
| 1 | **Q1 formal entscheiden** (Transform-Ops-Promotion; Reassessment empfiehlt Option C) + Decision-Doc erstellen | vor Gate 3 (harter Blocker) |
|  ܫ2 | Constraint-Scope für WP-04 bestätigen(Tool-Parameter vs. interaktive Hotkeys) | Gate 3/4-Planung |
|  ܫ3 | Cleanup freigeben(`src/core/move.py`, tote Tests-Kopien, `tests/mnt/`( | vor Merge |
|  ܫ4 | Teststrategie abnehmen(3 Ebenen, unten) | Gate 3-Start |
|  ܫ5 | E2E-Matrix definieren/abnehmen(Gate 10) | vor Gate 10 |
|  ܫ6 | GO/NO-GO für jedes Gate + finaler Merge-Entscheid | laufend |

## N. Empfehlung für das nächste Gate

1. **Das Repository ist für Gate 3 bereit — mit einer Vorbedingung.** Alle Suiten sind
   grün (Core 29+Verträge, Repo 62 unittest, Experiment 134 pytest); die
   Architektur-Boundaries sind durch den Code bestätigt; die Agent-Vorbereitung ist
   abgeschlossen.
2. **Q1 ist der einzige harte Blocker** für die Gate-3-Reihenfolge(entscheidet,
   ob Rotate/Scale-Operationen vor den Tools nach `src/core` wandern oder die Tools
   lokal implementiert werden). Die Reassessment-Doku empfiehlt klar „Option C (Promote +
   dokumentieren)“; mein Code-Review bestätigt: keine Vertragslücke, kein
   Core-Redesign nötig—es ist eine dokumentierte, minimale Erweiterung eines
   etablierten Musters.
3. **Claude wird für Gate 3 primär für die `app.py`-Extraktion und den
   Produktions-Entwurf von `src/mirai/` gebraucht**(K1/K2/K4). Mechanische Teile
   (Test-Migration, keymap-Validierung, Coverage-Messung, Spec-Pflege) kann der
   Agent übernehmen.**Für die Transform-Ops-Promotion selbst gilt:**kein
   Claude-Mehrwert bei Kopie/Exporten; Claude-Mehrwert nur bei der Freeze-
   Doku-Formulierung** — d.h. Claude ist für die eigentlich anspruchsvolle
   Architektur-Arbeit (app.py-Extraktion, modulare Produktions-Grenzen,
   Gesamt-Review) einzusetzen, nicht für mechanische Schritte.
4. **Teststrategie (3 Ebenen, WP-04):**
   - **A Core-Tests:** Operationen (Move; nach Q1: Rotate/Scale) + Constraints
     (Parameter-Semantik) + History-Vertrag. Ziel: window-frei, `unittest`, gegen `src/core`.
   - **B Production-Integration:** `Tool → Operation → Mesh/History` (Tool-Manager,
     Lifecycle, genau-1-History-Grenze, Cancel-Restore, Selection-Resolver) —
     Basis: experiment-tools-Suiten, migriert nach `src/mirai/interaction/tools/*`.
   - **C E2E/Manual:** `Application → Viewport → Input → Tool → Transform → History`
     (M/R/S, LMB-Drag/Release, Esc, Ctrl+Z/Y, Mode-Wechsel, Konstraints falls
     freigegeben). Human-Durchklick-Matrix mit PASS/FAIL je Zelle; Gate 10.
   - Prioritäten: A > B > C;Akzeptanzkriterien je Ebene in den Gate-Plänen bereits hinterlegt.

**Fazit:** Die Agent-Phase ist abgeschlossen.**WP-04 kann unverzüglich nach der**
**Q1-Entscheidung mit Gate 3 starten;Claude-Tokens werden dort eingesetzt, wo
**wirklicher Architektur-Mehrwert existiert — Rest übernimmt der Agent.**

---

**Report End**