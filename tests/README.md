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
python -m unittest tests.test_identity_continuity -v
python -m tests.test_core
```

## Struktur

| Modul | Hardening-Phase | Inhalt |
|---|---|---|
| `mesh_invariants.py` | A (Hilfe) | Katalog + `assert_mesh_invariants()` |
| `test_mesh_invariants.py` | A | Struktur-Invarianten, Boundary, gültige IDs |
| `test_topology_mutations.py` | B | split / collapse / connect (ID-Kontinuität, Adjazenz) |
| `test_identity_continuity.py` | C | split / collapse / connect: vollständige Vorher/Nachher-ID-Mengen-Diffs (was bleibt/stirbt/entsteht) |
| `test_core.py` | — | Architekturverträge AD-001/002/003, Serialisierung |

## Hardening-Ergebnis (2026-08-26, Phase A/B/C)

**Plan:** `docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md` §17 Phase A/B/C

**Gesamt: PASS** — 22 unittest-Tests + 11 Architekturvertrags-Blöcke, 0 Failures.

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

### Phase C – Identitätskontinuität (2026-08-26)

**Plan:** `docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md` §17 Phase C

Unterschied zu Phase B: Phase B prüfte die Gültigkeit *einzelner* IDs
("ist X noch gültig?"). Phase C vergleicht für jede Operation die
*vollständigen* Vertex-/Edge-/Face-ID-Mengen vor und nach der Mutation
(Mengendifferenz `entfernt = vorher − nachher`, `neu = nachher − vorher`),
damit auch nicht explizit erwartete Nebenwirkungen sichtbar würden.

| Operation | Szenario | Ergebnis |
|---|---|---|
| `split_edge` | Boundary-Edge (1 Face) | PASS — 1 neuer Vertex, 2 neue Edges, 1 entfernte Edge, Face-ID unverändert |
| `split_edge` | interne Edge (2 Faces) | PASS — beide Face-IDs bleiben unverändert erhalten, referenzieren danach beide den neuen Mittelpunkt |
| `collapse_edge` | einfacher Fall (Quad→Dreieck) | PASS — Survivor eindeutig v0, genau 1 Vertex + 1 Edge entfernt, keine neue ID, Face-ID bleibt |
| `collapse_edge` | Fan (dritte Kante wird umbenannt) | PASS — nur die kollabierte Edge verschwindet als ID; die dritte Kante behält ihre EdgeId, wechselt aber den Endpunkt (v1→v0) |
| `collapse_edge` | Merge-Zweig (bestehende survivor↔other-Edge) | PASS — zusätzlich zur kollabierten Edge verschwindet die jetzt-redundante zweite Edge; die degenerierte Face wird korrekt entfernt, die überlebende Diagonale referenziert danach nur noch die verbleibende Face |
| `connect_vertices` | Diagonalen-Split | PASS — alte Face-ID stirbt, 2 neue Face-IDs + 1 neue Edge-ID entstehen, alle Vertex-IDs und bestehenden Edges bleiben unverändert |

**Zusatzuntersuchung (laut Plan gefordert): Liefert der Core genug
Information, um „was bleibt/stirbt/entsteht" zuverlässig festzustellen?**

Ja, aber nur **extern rekonstruierbar**, nicht **proaktiv zurückgegeben**:
Ein Aufrufer kann über Vorher-/Nachher-Snapshots der Query-API
(`all_vertex_ids()`/`all_edge_ids()`/`all_face_ids()` + Mengendifferenz,
genau wie in `test_identity_continuity.py`) das vollständige Bild ableiten.
Die Mutationsfunktionen selbst geben aber nur ihre "Headline-IDs" zurück
(z. B. `collapse_edge()` nur den Survivor) — nicht die vollständige Liste
aller intern umbenannten/verschmolzenen/entfernten Nebenelemente (z. B.
die dritte Kante im Fan-Fall). Das deckt sich mit Plan §6–§8/§15: ein
dediziertes Change-Set/Herkunftssystem ist bewusst nicht Teil dieser
Phase. Für Phase C reicht das externe Rekonstruieren aus.

**Bewusst nicht getestet:** dieselben Einschränkungen wie Phase B
(konkrete Face-Zuordnung bei `connect_vertices`, Herkunfts-/Remapping-
Metadaten — weiterhin außerhalb des Scopes, siehe Plan §16).

**Produktionscode-Änderungen:** keine — alle Diffs entsprechen exakt den
bereits in `mesh.py` dokumentierten ID-Kontinuitäts-Verträgen.

### Architekturverträge (`test_core.py`)

Alle 11 Blöcke (AD-001 IDs, split, Query-API, connect, collapse ×2, AD-003 Lifecycle ×3, Selection, Serialisierung): **PASS**.

Invarianten-Checks wurden zusätzlich nach split/collapse/connect in `test_core.py` eingebunden.

## Fehler-Entscheidungsregel

Bei einem fehlgeschlagenen Test gilt:

1. **Test falsch?** — Erwartung widerspricht dokumentiertem Vertrag → Test anpassen.
2. **Core falsch?** — Vertrag klar, Implementierung verletzt ihn → Core fixen.
3. **Nicht spezifiziert?** — Keine Semantik erfinden; Test zurücknehmen oder als `skip` mit Verweis dokumentieren.

## Nächste Schritte (Plan §17, noch offen)

- Phase D: Undo/Redo für Topologieoperationen (split/collapse/connect)
- Phase E: Serialisierung nach Mutationen (Roundtrip mit Allocator-Zustand)
