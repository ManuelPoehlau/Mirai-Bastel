# Tests

Automatisierte Tests für Mesh-Topologie, Selection, Operations und History.

**Produktionspfad:** Alle Repository-Tests laufen gegen `src/core/` (nicht mehr gegen `experiments/mirai_bastel_core_V1/`).

## Ausführen

```bash
# Komplette Core-Testsuite (empfohlen)
python -m tests.run_core_suite

# Einzelne Module
python -m unittest tests.test_mesh_invariants -v
python -m unittest tests.test_topology_mutations -v
python -m tests.test_core
```

## Struktur

| Modul | Hardening-Phase | Inhalt |
|---|---|---|
| `mesh_invariants.py` | A (Hilfe) | Katalog + `assert_mesh_invariants()` |
| `test_mesh_invariants.py` | A | Struktur-Invarianten, Boundary, gültige IDs |
| `test_topology_mutations.py` | B | split / collapse / connect (ID-Kontinuität, Adjazenz) |
| `test_core.py` | — | Architekturverträge AD-001/002/003, Serialisierung |

## Hardening-Ergebnis (2026-08-26, Phase A/B)

**Plan:** `docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md` §17 Phase A/B

**Gesamt: PASS** — 16 unittest-Tests + 11 Architekturvertrags-Blöcke, 0 Failures.

### Phase A – Invarianten

| Test | Ergebnis |
|---|---|
| Leeres Mesh erfüllt Invarianten | PASS |
| Quad-Fixture erfüllt Invarianten | PASS |
| Invarianten nach `remove_face()` | PASS |
| Invarianten bei zwei Faces mit gemeinsamer Kante | PASS |
| `add_face()` lehnt unbekannte Vertex-ID ab | PASS |
| `add_face()` lehnt < 3 Vertices ab | PASS |

Geprüfte Invarianten (über Query-API):

- gültige Vertex-/Edge-/Face-Referenzen
- keine doppelten Vertices in Face-Boundaries
- bidirektionale Edge↔Face-Adjazenz
- keine Self-Loop-Edges
- max. 2 Faces pro Edge (manifold-V1-Annahme)
- keine stale Edge-Endpunkte nach Collapse (explizit in mesh.py dokumentiert)

**Produktionscode-Änderungen:** keine — alle Invarianten hält der Core.

### Phase B – Topologieoperationen

| Operation | Tests | Ergebnis |
|---|---|---|
| `split_edge` | ID-Kontinuität, Mittelpunkt-Position, interne Kante (2 Faces) | PASS |
| `collapse_edge` | Survivor v0, Geometrie, keine stale Endpunkte (Fan) | PASS |
| `connect_vertices` | ID-Kontinuität, zweite Diagonale (nur Invarianten), Fehlerfälle | PASS |

**Bewusst nicht getestet** (Semantik nicht spezifiziert):

- konkrete Face-Zuordnung bei `connect_vertices` (welches Dreieck welche Vertices enthält bei Diagonale v1–v3 vs. v0–v2)
- Herkunfts-/Remapping-Metadaten für spätere Skin/Morph-Systeme (Phase C+)

**Produktionscode-Änderungen:** keine.

### Architekturverträge (`test_core.py`)

Alle 11 Blöcke (AD-001 IDs, split, Query-API, connect, collapse ×2, AD-003 Lifecycle ×3, Selection, Serialisierung): **PASS**.

Invarianten-Checks wurden zusätzlich nach split/collapse/connect in `test_core.py` eingebunden.

## Fehler-Entscheidungsregel

Bei einem fehlgeschlagenen Test gilt:

1. **Test falsch?** — Erwartung widerspricht dokumentiertem Vertrag → Test anpassen.
2. **Core falsch?** — Vertrag klar, Implementierung verletzt ihn → Core fixen.
3. **Nicht spezifiziert?** — Keine Semantik erfinden; Test zurücknehmen oder als `skip` mit Verweis dokumentieren.

## Nächste Schritte (Plan §17, noch offen)

- Phase C: Identitätskontinuität explizit (was bleibt/stirbt/entsteht)
- Phase D: Undo/Redo für Topologieoperationen
- Phase E: Serialisierung nach Mutationen (Roundtrip mit Allocator-Zustand)
