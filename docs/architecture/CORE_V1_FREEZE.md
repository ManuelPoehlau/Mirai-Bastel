# Mirai-Bastel Core V1 — Produktions-Freeze

**Status:** FROZEN (with authorized exceptions; see §7.1)
**Datum:** 2026-08-27
**Revidiert:** 2026-09-24 (AD-SYM-01 SymmetryDefinition extension added); previously 2026-09-22 (AD-017 split_edge(t) extension added); previously 2026-09-17 (AP-05 `add_edge()` precedent added; previously 2026-09-04, ADR-001 precedent added)
**Grundlage:** Hardening-Phasen A–E + Gesamtarchitektur-Review

## 1. Entscheidung

`src/core/` wird nach Abschluss des Hardening- und Architektur-Reviews als **Core V1 eingefroren**.

Freeze bedeutet nicht, dass der Core niemals wieder geändert werden darf. Es bedeutet:

> Eine Änderung an `src/core/` benötigt ab jetzt eine konkrete neue Anforderung, die zeigt, dass der bestehende V1-Vertrag nicht ausreicht.

Zukünftige Systeme werden nicht vorsorglich in den Core eingebaut.

### §7.1 Authorized Exceptions (Precedent)

**Decision:** ADR-001 (2026-09-04, ACCEPTED)

Transform operations (`RotateOperation`, `ScaleOperation`) are promoted from experiments to `src/core/operations/transform.py` as authorized production extensions.

**Rationale:** These operations are fundamental modeling operations, not speculative future systems. They are production-grade (per Gate 2 classification) and belong in Core as first-class citizenship.

**Process for future exceptions:** Follow same analysis as ADR-001 (classify operation, justify promotion, document precedent).

**Decision:** AP-05 (2026-09-14, commit `50fbee8`)

`Mesh.add_edge()` is promoted from the topology experiment (Connect Edges' "kind v" / FreeConnect
case) to `src/core/mesh.py` as an authorized production extension — a minimal, public mutation
primitive for a free edge between two vertices without a shared face. Covered by an
architecture-contract test including error cases and invariants (`tests/test_core.py:128-165`).
Follows exactly the flow this document's own §7 (below) and `docs/architecture/ROADMAP.md §13`
describe: experiment demonstrated the need (Connect Edges' "kind v" case), finding documented, Core
extended, existing methods (`split_edge`/`connect_vertices`) left unchanged.

**Decision:** AD-017 (2026-09-22)

`Mesh.split_edge(edge_id, t=0.5)` is extended with an optional `t` parameter (default 0.5,
bit-identical to the existing midpoint behaviour). Rationale: Knife mode makes non-midpoint splits
the normal case; the documented "splits at the midpoint" contract would otherwise misrepresent the
result; the rigging experiment's midpoint-matching fallback (FINDINGS-3C, 3C-2) fails for t ≠ 0.5,
leaving the (edge, t) pair as the reliable provenance path (AD-017 B5/B1b). Backward compatible:
all callers that call `split_edge(eid)` are unaffected. Covered by new contract tests in
`tests/test_core.py`. `Mesh.add_edge()` retained unchanged; no active production consumer after
strip Connect was rejected; retained for potential future construction/curve work (AD-017 §13).

**Decision:** AD-SYM-01 (2026-09-24, WP-SYM-01 Slice 1)

`Mesh` gains a `symmetry_definition: SymmetryDefinition | None` attribute (`src/core/mesh.py`) —
Plane (point + unit normal) and a declared set of Seam `EdgeId`s, default `None` ("symmetry off").
Authorized by `docs/architecture/AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md` (DECIDED): the
Definition is bound to the Mesh's own ID space and must not outlive a Mesh replacement or
desynchronize from an Undo — both already hold for Mesh's own containers, neither holds for a
Scene-level location (measured regression in AD-SYM-01 §1.1). `export_state()`/`load_state()` gain
an additive, optional `"symmetry"` key (no `FORMAT_VERSION` bump; `state.get("symmetry")` so a dict
without the key still loads); `MeshStateCommand` therefore carries the Definition through Undo/Redo
without any new History machinery (AD-SYM-02 §5). Mesh stores this declaration only — it does not
interpret it; Correspondence-Ableitung and State-Aggregation live in `src/mirai/symmetry.py`
(outside the frozen Core, same placement rationale as `scene_factory.py`/`mesh_geometry.py`,
AD-008). Covered by `tests/test_symmetry.py` (storage/roundtrip, the AD-SYM-01 §1.1 regression case,
all four Correspondence states, all Symmetry State outcomes) and a roundtrip regression added to
`tests/test_scene_serialization.py`. No operation, tool, or Undo/Redo *behavior* for the Definition
itself in this slice (Definition is set directly, e.g. `mesh.symmetry_definition = ...`) — that is
explicitly out of scope for WP-SYM-01 Slice 1.

## 2. Was vor dem Freeze validiert wurde

### Phase A — Invarianten

- gültige Vertex-/Edge-/Face-Referenzen
- keine doppelten Vertices in Face-Boundaries
- bidirektionale Edge↔Face-Adjazenz
- keine Self-Loops
- maximal zwei Faces pro Edge für die V1-Manifold-Annahme
- keine stale Edge-Endpunkte nach Collapse

### Phase B — Topologie

`split_edge`, `collapse_edge` und `connect_vertices` wurden in relevanten Boundary-/Interior-/Fan-/Merge-Szenarien geprüft.

### Phase C — Identitätskontinuität

Für jede Topologieoperation wurden die vollständigen Mengen von Vertex-, Edge- und Face-IDs vor und nach der Mutation verglichen. Damit ist nicht nur die Existenz einzelner IDs, sondern auch nachvollziehbar, welche Elemente bleiben, verschwinden oder neu entstehen.

Der Core liefert dafür bewusst noch kein allgemeines Change-Set-/Provenance-System. Die vollständigen Diffs sind über die öffentliche Query-API extern rekonstruierbar.

### Phase D — Undo / Redo

Topologieänderungen können über `MeshStateCommand` mit Vorher-/Nachher-Snapshots exakt rückgängig gemacht und wiederhergestellt werden.

`Mesh.load_state()` stellt den Zustand in-place wieder her. Der ID-Allocator bleibt dabei monoton; Undo darf keine bereits verwendete ID erneut verfügbar machen.

Die Topologie-Mutationen bleiben bewusst History-unabhängig. Ein Aufrufer entscheidet explizit, wann eine atomare Mutation als History-Command erfasst wird.

### Phase E — Serialisierung

Scene-/Mesh-Zustände wurden nach echten Topologie-Mutationssequenzen per Dict und JSON roundtripped.

Geprüft wurden unter anderem:

- vollständige Topologiebeziehungen
- exakte Allocator-Zählerstände
- Kollisionsfreiheit für Vertex/Edge/Face-IDs nach dem Laden
- bewusster Ausschluss von Selection und History aus der Persistenz
- reservierte V1-Subsystem-Plätze für Morph Targets, Rig und Animation
- Versionsprüfung
- leere Scene

Die reproduzierbare Standard-Core-Suite umfasst **29 `unittest`-Tests**. Die Architekturverträge aus `tests/test_core.py` werden anschließend separat ausgeführt und enthalten zusätzlich die Basis-Serialisierungsprüfungen. Die dedizierten 8 Phase-E-Tests in `tests/test_scene_serialization.py` existieren als ergänzende, separat ausführbare Regressionstests, sind aber aktuell **nicht Bestandteil von `tests.run_core_suite`**.

**Gesamtergebnis der Standard-Suite:** 29/29 `unittest`-Tests + Architekturvertrags-Checks, PASS.

## 3. Architekturabgleich mit der langfristigen Vision

Die langfristige Vision ist kein größerer Modellierer um seiner selbst willen, sondern ein lebendes, erweiterbares 3D-System, in dem Modellierung, Deformation, Rigging, Morphs und Animation auf einer gemeinsamen Scene weiterarbeiten können.

Der V1-Core verbaut diese Richtung nicht:

- stabile opaque IDs schaffen eine Grundlage für spätere Referenzen
- kontrollierte Topologie-Queries verhindern, dass spätere Systeme von konkreten Containern abhängen müssen
- History und Serialization sind eigenständige Core-Verantwortlichkeiten
- UI, Viewport und Renderer sind nicht Teil des Core
- zukünftige Deformations-/Morph-/Rig-Systeme sind nicht vorweggenommen

Wichtig: **Stable IDs allein lösen noch kein Skin-/Morph-Remapping.** Bei zukünftigen Topologieänderungen wird voraussichtlich ein zusätzliches Change-/Provenance-/Remapping-Konzept benötigt. Dieses gehört in eine spätere, durch konkrete Anforderungen motivierte Phase.

Damit bleibt insbesondere der gewünschte langfristige Workflow möglich:

```text
Model
  ↓
Rig / Deformation testen
  ↓
fehlende Geometrie erkennen
  ↓
Mesh weiter bearbeiten
  ↓
Deformation / Animation weiterverwenden
```

Der V1-Core muss diesen Workflow noch nicht vollständig implementieren; er darf ihn aber nicht durch falsche V1-Annahmen unnötig verhindern.

## 4. Bewusst NICHT Teil des Freeze

Folgende Systeme werden nicht nachträglich in Core V1 hineingezogen:

- Half-Edge-/Winged-Edge-Neuimplementierung
- generisches Change-Set-System
- Herkunfts-/Provenance-Metadaten
- Skin-Weight-Remapping
- Morph Targets
- Rigging / Bones
- Animation
- Soft Selection / Influence-System
- vollständiges Extension-/Plugin-System
- AI-Integration
- Renderer
- UI / Viewport

Diese Punkte bleiben zukünftige Architektur- und Implementierungsaufgaben.

## 5. Konsequenz für `src/`

`src/core/` ist ab diesem Punkt **Referenz- und Vertragsbasis** für die nächsten Produktionsschichten.

Neue Produktionssysteme sollen den Core konsumieren, nicht ihn für jede neue UI-/Viewport-/Tool-Anforderung umbauen.

Grundrichtung:

```text
UI ──────────┐
             │
Tools ───────┼──► Core (FROZEN V1)
             │
Viewport ────┘
```

Die konkrete Produktionsstruktur außerhalb des Core wird erst aus den inzwischen gewachsenen Experimenten und echten Anforderungen abgeleitet.

## 6. Beziehung zu den Experimenten

Die Experimente bleiben bewusst erhalten. Sie sind Erkenntnis- und Validierungsräume, keine automatisch zu übernehmenden Produktionsmodule.

Insbesondere der Viewport-V1-Praxistest hat die Core→Viewport-Schnittstelle praktisch validiert, ist aber weiterhin ein Experiment.

## 7. Freeze-Regel für die Zukunft

Vor einer Änderung am gefrorenen Core gilt:

1. konkrete neue Anforderung benennen
2. prüfen, ob sie mit den bestehenden öffentlichen APIs lösbar ist
3. falls nicht: Architekturproblem dokumentieren
4. kleinste notwendige Core-Erweiterung bestimmen
5. Tests/Vertrag ergänzen
6. Änderung erst dann durchführen

Damit bleibt V1 klein, stabil und verständlich, ohne die Weiterentwicklung des Gesamtsystems zu blockieren.
