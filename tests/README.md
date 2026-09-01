# Tests

Automatisierte Tests für Mesh-Topologie, Selection, Operations, History und Serialisierung.

**Produktionspfad:** Alle Repository-Tests laufen gegen `src/core/` (nicht gegen `experiments/mirai_bastel_core_V1/`).

## Ausführen

```bash
# Komplette Core-Testsuite (empfohlen)
python -m tests.run_core_suite

# Einzelne Module
python -m unittest tests.test_mesh_invariants -v
python -m unittest tests.test_topology_mutations -v
python -m unittest tests.test_identity_continuity -v
python -m unittest tests.test_topology_history -v
python -m unittest tests.test_scene_serialization -v
python -m tests.test_core
```

## Struktur

| Modul | Hardening-Phase | Inhalt |
|---|---|---|
| `mesh_invariants.py` | A (Hilfe) | Katalog + `assert_mesh_invariants()` |
| `test_mesh_invariants.py` | A | Struktur-Invarianten, Boundary, gültige IDs |
| `test_topology_mutations.py` | B | split / collapse / connect (ID-Kontinuität, Adjazenz) |
| `test_identity_continuity.py` | C | vollständige Vorher/Nachher-ID-Mengen-Diffs |
| `test_topology_history.py` | D | commit → undo → redo, exakter Zustand inkl. IDs und Beziehungen |
| `test_scene_serialization.py` | E | Dict-/JSON-Roundtrip nach Mutationen, Allocator, Kollisionen, Versionsprüfung |
| `test_core.py` | — | Architekturverträge AD-001/002/003, Basis-Serialisierung |
| `test_history_contract.py` | WP-04 | HistoryStack-Vertrag (No-op-undo/redo, Redo-Zweig-Verwerfen, LIFO) — separat ausführbar |
| `test_operation_lifecycle.py` | WP-04 | Operation-Lifecycle-Guards (AD-003: begin/update/commit/cancel-State-Machine, History-Grenzen, No-op/Boundary) — separat ausführbar |

## Hardening-Ergebnis (2026-08-27)

**Phasen A–E: PASS.** Die reproduzierbare Standard-Suite `tests.run_core_suite` umfasst aktuell **29 `unittest`-Tests** und führt anschließend die Architekturvertrags-Checks aus `tests.test_core` aus. Der Lauf endet mit `Gesamt: PASS` und 0 Failures/Errors.

Die dedizierten **8 Phase-E-Tests** in `test_scene_serialization.py` sind zusätzliche Regressionstests und können separat ausgeführt werden; sie sind aktuell bewusst noch nicht in `run_core_suite.py` eingebunden. Die Architekturvertrags-Checks enthalten bereits eigene Basis-Serialisierungsprüfungen.
Seit der WP-04-Verification (2026-09-01) existieren zusätzlich die
**25 WP-04-Regressionstests** in `test_history_contract.py` (10) und
`test_operation_lifecycle.py` (15): sie prüfen die HistoryStack-Verträge
(Redo-Zweig-Verwerfen, No-op-undo/redo) und die Operation-Lifecycle-Zustandsguards
(AD-003) explizit. Sie sind — wie die Phase-E-Tests — bewusst **nicht Teil des
Standard-Runners** `run_core_suite` (sondern separat ausführbar
(`python -m unittest tests.test_history_contract -v` usw.), damit die dokumentierte
„29/29“-Standard-Baseline stabil bleibt. Alle 62 `unittest`-Tests des
`tests/`-Verzeichnisses sind grün (`python -m unittest discover -s tests -p test_*.py`).

### Phase A – Invarianten

Geprüft wurden gültige Referenzen, keine doppelten Face-Vertices, bidirektionale Edge↔Face-Adjazenz, keine Self-Loops, maximal zwei Faces pro Edge sowie keine stale Edge-Endpunkte nach Collapse.

**Produktionscode-Änderungen:** keine.

### Phase B – Topologieoperationen

`split_edge`, `collapse_edge` und `connect_vertices` wurden in Boundary-, Interior-, Fan- und Merge-Szenarien sowie mit Fehlerfällen geprüft.

**Produktionscode-Änderungen:** keine.

### Phase C – Identitätskontinuität

Für jede Topologieoperation wurden die vollständigen Vertex-/Edge-/Face-ID-Mengen vor und nach der Mutation verglichen. Damit ist extern über die Query-API nachvollziehbar, welche Elemente bleiben, verschwinden oder entstehen.

Ein allgemeines Change-Set-/Provenance-System ist weiterhin bewusst außerhalb des V1-Scopes.

**Produktionscode-Änderungen:** keine.

### Phase D – Undo / Redo für Topologieoperationen

Vor der Testimplementierung wurde festgestellt, dass Topologieoperationen keine History-Anbindung hatten. Für exaktes Undo inklusive ursprünglicher ID-Mengen ist wegen des monotonen AD-001-ID-Allocators ein semantischer Inverse-Ansatz ungeeignet. Daher wurde minimal `Mesh.load_state()` für In-Place-Restore und `MeshStateCommand` für Vorher-/Nachher-Snapshots ergänzt.

Getestet wurden split (Boundary/Interior), collapse (einfach/Fan/Merge), connect sowie Mehrfachsequenzen mit undo/redo. Zusätzlich wird explizit geprüft, dass Undo keine alte ID wiederverwendbar macht.

**Produktionscode-Änderungen:** `mesh.py`, `operations/topology.py`, `operations/__init__.py`, `history.py`.

### Phase E – Serialisierung nach Mutationen

Vor der Testimplementierung wurde geprüft, ob der vorhandene Core die Anforderungen bereits erfüllt. `export_state()` / `load_state()` / `scene_to_dict()` / `scene_from_dict()` deckten den geplanten Umfang ab; Phase E benötigte deshalb **keine Produktionscode-Änderung**.

Die 8 dedizierten Tests prüfen:

- Dict-Roundtrip nach einer echten Sequenz aus `split_edge` + `collapse_edge` + weiterer Topologieänderung
- vollständige Topologiebeziehungen nach dem Roundtrip
- JSON-Roundtrip
- exakte Vertex-/Edge-/Face-Allocator-Zählerstände
- Kollisionsfreiheit neuer IDs nach dem Laden für alle drei Elementtypen
- bewussten Ausschluss von Selection und History aus der Persistenz
- reservierte V1-Slots für `morph_targets`, `rig` und `animation`
- Ablehnung unbekannter Format-Versionen
- verlustfreien Roundtrip einer leeren Scene

**Produktionscode-Änderungen:** keine.

## Gesamtabschluss

Mit Phase E sind die geplanten Hardening-Phasen A–E abgeschlossen und grün:

```text
A  Invarianten             PASS
B  Topologie               PASS
C  Identitätskontinuität   PASS
D  Undo / Redo             PASS
E  Serialisierung          PASS

Standard-Suite: 29/29 unittest-Tests
+ Architekturvertrags-Checks
= 0 Failures / Errors
```

Die zusätzlichen 8 Phase-E-Regressionstests bleiben separat ausführbar und sind derzeit nicht Teil des Standard-Runners.

Der anschließende Architektur-Review ist in `docs/architecture/CORE_V1_FREEZE.md` dokumentiert. Ergebnis: **Core V1 wird eingefroren.**

## Fehler-Entscheidungsregel

Bei einem fehlgeschlagenen Test gilt:

1. **Test falsch?** — Erwartung widerspricht dokumentiertem Vertrag → Test anpassen.
2. **Core falsch?** — Vertrag klar, Implementierung verletzt ihn → Core fixen.
3. **Nicht spezifiziert?** — Keine Semantik erfinden; Test zurücknehmen oder als `skip` mit Verweis dokumentieren.

## Nach dem Freeze

Die Tests bleiben als Regression-Suite bestehen. Neue Anforderungen an den gefrorenen Core benötigen einen dokumentierten Architekturgrund und neue Tests, bevor der Core-Vertrag geändert wird.
