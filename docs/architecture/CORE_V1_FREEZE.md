# Mirai-Bastel Core V1 — Produktions-Freeze

**Status:** FROZEN (with authorized exceptions; see §7.1)
**Datum:** 2026-08-27
**Revidiert:** 2026-10-06 (WP Delete/Dissolve: `Mesh.dissolve_vertex/dissolve_edges/dissolve_faces` and `delete_vertices/delete_edges/delete_faces` added); previously 2026-10-01 (AD-017 K1 `Mesh.split_face` extension added, WP-KNIFE-00); previously 2026-09-24 (AD-SYM-02 symmetric Move extension added, WP-SYM-01 Slice 2); previously 2026-09-24 (AD-SYM-01 SymmetryDefinition extension added); previously 2026-09-22 (AD-017 split_edge(t) extension added); previously 2026-09-17 (AP-05 `add_edge()` precedent added; previously 2026-09-04, ADR-001 precedent added)
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

**Decision:** AD-SYM-02 (2026-09-24, WP-SYM-01 Slice 2)

`Operation` (`src/core/operation.py`) gains `supports_symmetry: bool = False`, a class attribute
following the same precedent as `description` — an Operation-level statement, not touching the
lifecycle, abstractly queryable before any `begin()` and even without an instance. `MoveOperation`
overrides it to `True`; `RotateOperation`/`ScaleOperation` keep the default `False` (symmetric
Rotate/Scale is explicitly out of scope for this slice). Authorized by
`docs/architecture/AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md` (DECIDED) §2.3.

`VertexTransformOperation._on_update()` (`src/core/operations/transform.py`) additionally passes
`vertex_id=vid` into `_transform_position()` — the one minimal extension of the shared Move/
Rotate/Scale loop needed for per-vertex differentiation (analogous to the existing `self._weights`
soft-selection placeholder). `RotateOperation`/`ScaleOperation` are unaffected (both already accept
arbitrary kwargs via `**_`); only `MoveOperation` (`src/core/operations/move.py`) uses it, to apply
one of three vertex-category deltas per AD-SYM-02 §2.4: directly selected vertices get the plain
`delta`; mirrored partner vertices (inferred via `mirai.symmetry.vertex_correspondence()`, resolved
by `MoveTool` before `begin()`, never a vertex already part of the Artist's explicit selection — see
`core/operations/move.py` module docstring for the full edge-case rationale) get the delta *vector*
reflected across `plane_normal` (`d' = d - 2*(d·n)*n`); Seam vertices among the selected get the
delta projected onto the plane (`d_proj = d - (d·n)*n`, INV-2). The symmetry context travels through
the existing, unmodified `OperationContext.params["symmetry"]` (same channel `pivot` already uses,
AD-SYM-02 §2.2) — no new field on `OperationContext`, no `MirrorResult` structure, no History
extension: one symmetric Move is still exactly one `Operation` instance and exactly one History
entry (AD-SYM-02 §2.1, already guaranteed by the existing `Operation.commit()` contract). Covered by
`tests/test_symmetric_move.py` (mirrored-delta math, the mirror invariant held after the move,
multi-update incrementality, single History entry + Undo/Redo across both sides, Cancel restoring
both sides exactly, Seam projection staying exactly on the plane, the unaffected no-symmetry
regression case, the explicit-both-sides-selected edge case, and the `supports_symmetry` flag) plus
`SymmetricMoveIntegrationTests` in `tests/test_tool_integration.py` (same behavior through the real
`MoveTool`/`Application` pipeline, not just the Operation layer). `mirai.symmetry` additionally gains
`mirrored_selection()` (pure function, no cache, AR-1) — covered by `TestMirroredSelection` in
`tests/test_symmetry.py`.

**Decision:** AD-017 K1 (2026-10-01, WP-KNIFE-00)

`Mesh.split_face(face_id, v_a, v_b, positions=())` is added to `src/core/mesh.py` as an authorized production
extension — one additive primitive that splits a face along a path `v_a → positions… → v_b` (the B2c sketch of
`docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md` §3). Rationale: the Artist KEEP'd the Q5 face constructions
(notch, closed shape, loop at a point) and chose K1 for the One Knife (Manu, 2026-10-01); the public API can build
them only by face surgery in the tool (`remove_face` + `add_vertex` + `add_face`), which contradicts AD-017 B5 and
the V1_SPEC mutation-layer principle; a primitive that knows the parent face, the path and both sides is also the
natural provenance hook (ARCH-02). With `positions == ()` it is bit-identical to `connect_vertices` (one documented
refusal more: a chord that is already an edge of another face). The accepted contract and the freeze-rule table are
in `docs/architecture/AD-017_FINAL_DECISIONS_2026-09-22.md`, Addendum 2026-10-01. Covered by the `test_split_face_*`
contract tests in `tests/test_core.py` (ID continuity, `connect_vertices` twin, notch, unchanged mesh incl. allocator
counters on every error, winding, both argument orders, serialization and `MeshStateCommand` Undo/Redo round trips,
symmetry definition untouched) and by `playground/tests/test_split_face_equivalence.py` (same faces as the Lab
stand-ins on grid, cube and head). `connect_vertices` and `split_edge` unchanged; no new `Operation`, no
serialization change.

**Decision:** AD-SYM-02 §2.4 follow-up (2026-10-03, WP-SYM-LAB-02 S2)

`RotateOperation`/`ScaleOperation` (`src/core/operations/transform.py`) become symmetric the same way
`MoveOperation` did, and flip `supports_symmetry` to `True` (both inherit it from a new private
intermediate class `_PivotTransformOperation(VertexTransformOperation)`; `Move`, `Operation`,
`OperationContext` and History are untouched). The symmetry context travels through the existing
`OperationContext.params["symmetry"]` (`plane_normal`, `mirrored_vertex_ids`, `seam_vertex_ids`, plus
`plane_point` — a pivot is a *position* and can only be mirrored with a plane point). Three vertex
categories, one interaction, one History entry: directly selected vertices get the ordinary transform
about the pivot; mirrored partners get the *conjugated intent* — rotation about mirror(pivot) around
mirror(axis) by −angle, scale about mirror(pivot) with factor b_i applied along mirror(b_i) (a
reflection reverses handedness), computed as `mirror(T(mirror(p)))` so the partner is the *bit-exact*
mirror of the source position (`mirai.symmetry` finds partners by exact position equality, AR-1; an
approximation would silently degrade a pair to UNPAIRED); Seam vertices get the ordinary transform,
projected exactly onto the plane afterwards. The Operation hard-codes no centroid: the pivot is
`params["pivot"]` (mirrored for partners) or, as before, the centroid of the affected vertices;
`RotateTool`/`ScaleTool` (shared `TransformTool._on_begin`, helper `resolve_symmetry()` in
`selection_helpers.py`, same resolution as `MoveTool.begin()`) pass the affected set (selection ∪
partners; an explicitly selected partner wins and the pair then moves as a rigid group) and, when no
pivot is given under symmetry, the centroid over selection ∪ partners (a single vertex turns about the
pair midpoint). *Superseded 2026-10-03 (Artist decision, WP-SYM-LAB-03 joint session, `src/mirai`
only, no Core change):* the default is now the centroid of the explicit selection, per side, mirrored
for the partners by the operation; fallback to selection ∪ partners when a seam vertex is affected and
the own centroid is off the plane (`selection_helpers.symmetric_default_pivot`). Seam contract (INV-2/INV-8): a Seam vertex stays on the plane only if the pivot is on
the plane AND rotation axis ∥ plane normal / scale is uniform or normal-aligned (normal is an
eigenvector of the scale matrix); otherwise the tool refuses *before the first motion* with the new
`SeamConstraintError` (the Operation raises the same error as a backstop, before touching any vertex).
Agent assumption: "on the plane / parallel" is decided with an absolute tolerance
`SEAM_TOLERANCE = 1e-9`, inside which the Seam result is projected exactly onto the plane (centroids
carry ~1e-17 rounding residue; the existing VIOLATED check is exact). Production behaviour is
unchanged: no symmetry can be switched on in the Production app, so `params` carries no `"symmetry"`
key and the maths is the previous code path (asserted in `tests/test_symmetric_transform.py`).
Covered by `tests/test_symmetric_transform.py` (bit-exact mirror equivalence over random axes/angles/
factors and 60 incremental updates with pivot on and off plane, oblique-plane tolerance case,
documented-formula equivalence, rotation sense for normal vs. in-plane axis, single vertex, rigid
explicit pair, Seam allow/refuse cases staying exactly on the plane, cancel/commit/Undo) and
`tests/test_symmetric_move.py` (flag flipped). Free pivots and a pivot UI remain out of scope.

**Decision:** WP Delete/Dissolve (2026-10-06, `docs/WP_DELETE_DISSOLVE_PLAN.md`)

Six additive removal primitives are added to `src/core/mesh.py` as an authorized production extension: the
preserving `dissolve_vertex(vertex_id)`, `dissolve_edges(edge_ids, *, cleanup)`, `dissolve_faces(face_ids, *,
cleanup)` and the destructive `delete_vertices(vertex_ids)`, `delete_edges(edge_ids)`, `delete_faces(face_ids)`.
Freeze rule (§7): (1) requirement — Delete/Dissolve on all three element levels in the Production app (Artist
decisions Manu 2026-10-06, plan §0.2); until now collapse was the only removal. (2) Not solvable with the public API:
no public operation removes an edge or a vertex, and merging faces through `remove_face` + `add_face` is the same face
surgery in the tool that AD-017 B5 / K1 ruled out. (3)/(4) Smallest extension: one internal planner
(`_region_outline` / `_plan_dissolve`, read-only, every precondition checked before the first mutation — on
`MeshError` the mesh incl. allocator counters is unchanged) and one apply step shared by all three dissolves; one
internal delete core shared by the three deletes. Decisions made while building (plan Status: "beim Bauen
entschieden"): `cleanup` is keyword-only without a default (the variant is a binding choice, §0.2.2, and part of the
public signature, never silent); the plan's `dissolve_edge(edge_id, cleanup)` became `dissolve_edges(edge_ids, *,
cleanup)` — atomic over a selection, because with per-edge cleanup the first edge can remove the endpoint the next
selected edge hangs on (two edges at a cube corner); for one edge it is the plan's operation. Vertex and Edge Delete
got own primitives (no public edge removal exists); Delete removes the given elements, their faces, every edge of
those faces that is left without a face (inner edges and former mesh-border edges alike) and vertices left without an
edge; edges still used by a remaining face stay as the hole border (plan §0.2.3 as clarified by Manu 2026-10-06: "a
floating edge goes"). `remove_face` keeps its V1 contract (edges stay). A dissolve that merges faces creates one new `FaceId`
per region (all region `FaceId`s become invalid); removing a 2-valent vertex creates one new `EdgeId` per chain and
keeps the neighbour face's `FaceId` (its boundary loses the vertex) — the exact inverse of `split_edge` up to the new
id. Each method documents its ID continuity in the docstring. `collapse_edge`, `remove_face` and every existing
method unchanged; the Symmetry Definition is not touched (symmetry behaviour is out of scope); no new `Operation`, no
serialization change; Undo/Redo through the existing `MeshStateCommand`. Covered by
`tests/test_core_delete_dissolve.py` (43: ID continuity, no-op, error with unchanged state incl. counters, the
2×2-grid cases (corner face, two faces), cube both variants, 3×3 loop to pure quads, shared chain, degenerate/existing-edge skips, hole and
self-touching regions, bowtie, winding, MeshStateCommand Undo/Redo + serialization round trip, symmetry definition
untouched) and `tests/test_application_delete_dissolve.py` (Production path).

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
