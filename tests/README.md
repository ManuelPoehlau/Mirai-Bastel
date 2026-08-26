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
python -m unittest tests.test_topology_history -v
python -m tests.test_core
```

## Struktur

| Modul | Hardening-Phase | Inhalt |
|---|---|---|
| `mesh_invariants.py` | A (Hilfe) | Katalog + `assert_mesh_invariants()` |
| `test_mesh_invariants.py` | A | Struktur-Invarianten, Boundary, gültige IDs |
| `test_topology_mutations.py` | B | split / collapse / connect (ID-Kontinuität, Adjazenz) |
| `test_identity_continuity.py` | C | split / collapse / connect: vollständige Vorher/Nachher-ID-Mengen-Diffs (was bleibt/stirbt/entsteht) |
| `test_topology_history.py` | D | split / collapse / connect: commit → undo → redo, exakter Zustand (ID-Mengen + Beziehungen) |
| `test_core.py` | — | Architekturverträge AD-001/002/003, Serialisierung |

## Hardening-Ergebnis (2026-08-26, Phase A/B/C/D)

**Plan:** `docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md` §17 Phase A/B/C/D

**Gesamt: PASS** — 29 unittest-Tests + 11 Architekturvertrags-Blöcke, 0 Failures.

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

### Phase D – Undo/Redo für Topologieoperationen (2026-08-26)

**Plan:** `docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md` §17 Phase D

**Vorab-Befund (vor jeder Testimplementierung geklärt, nicht eigenmächtig
entschieden):** `split_edge`/`collapse_edge`/`connect_vertices` hatten vor
dieser Phase **keine** History-Anbindung — nur `MoveOperation` erzeugte
einen Command. Phase D setzt „commit → undo → redo" aber voraus, das
musste also zuerst geschaffen werden.

**Zweiter, wichtigerer Befund:** Ein semantischer Inverse-Ansatz (Undo
durch eine Gegenoperation, analog `MoveVerticesCommand`) kann die
Anforderung „exakter ursprünglicher Zustand inkl. ID-Mengen" grundsätzlich
nicht erfüllen — AD-001 verbietet ID-Wiederverwendung innerhalb einer
Session für immer, auch nach dem Löschen des Elements. Jede Mutation, die
im Zuge einer Gegenoperation neue Elemente erzeugt, bekäme zwangsläufig
neue IDs statt der ursprünglichen. Ein vollständiger Zustands-Snapshot
(`Mesh.export_state()`/`load_state()`) ist damit nicht nur pragmatischer,
sondern die einzige Möglichkeit, exakte ID-Kontinuität über Undo/Redo
hinweg zu garantieren.

**Umgesetzt (minimal, wie mit Nutzer abgestimmt):**

- `Mesh.load_state(state)` — neue Instanzmethode, ersetzt den Mesh-Inhalt
  in-place (im Unterschied zum bestehenden `from_state()`-Classmethod, das
  ein neues Objekt erzeugt). `from_state()` ruft jetzt intern
  `load_state()` auf (Entduplizierung, keine Verhaltensänderung).
  Allocator-Zähler werden wie zuvor nur vorwärts gesetzt
  (`restore_counter()`) — beim Undo bleibt der Zähler deshalb auf dem
  höheren, aktuellen Stand, statt zurückzuspringen (AD-001-konform,
  explizit mit einer Kontrollprobe getestet).
- `operations/topology.py::MeshStateCommand` — generisches Command
  (`undo()`/`redo()`), das Vorher-/Nachher-Snapshots hält. Keine
  automatische Kopplung an Mesh-Mutationen; Aufrufer (hier: die Tests)
  bauen das Command explizit um ihren Mutationsaufruf herum.
- `history.py`-Docstring korrigiert: `push()` wird nicht mehr
  ausschließlich von `Operation.commit()` aufgerufen, sondern auch direkt
  für atomare Mutationen ohne Operation-Lebenszyklus (dokumentierte
  Ausnahme, keine Verhaltensänderung an `HistoryStack` selbst).

| Operation | Szenario | Ergebnis |
|---|---|---|
| `split_edge` | Boundary-Edge, commit→undo→redo | PASS — exakter Zustand (ID-Mengen + alle Beziehungen) in beide Richtungen |
| `split_edge` | interne Edge (2 Faces), commit→undo→redo | PASS — beide Faces korrekt zurück-/wiederhergestellt |
| `collapse_edge` | einfacher Fall, commit→undo→redo | PASS |
| `collapse_edge` | Fan (umbenannte dritte Edge), commit→undo→redo | PASS — Edge zeigt nach undo() wieder exakt auf v1, nach redo() exakt auf v0 |
| `collapse_edge` | Merge-Zweig (Edge+Face sterben), commit→undo→redo | PASS — beide mit identischer ID wiederhergestellt |
| `connect_vertices` | Diagonalen-Split, commit→undo→redo | PASS |
| Mehrfach-Sequenz | split → collapse → undo×2 → redo×2 | PASS — HistoryStack steppt korrekt durch mehrere MeshStateCommands |

**AD-001-Kontrollprobe:** nach `undo()` eines Splits erzeugt eine
anschließende neue Mutation nachweislich eine höhere, nie zuvor
vergebene ID — die ID des rückgängig gemachten Elements wird nicht
wiederverwendet (explizit assertet in `test_topology_history.py`).

**Bewusst nicht verändert:** keine neue allgemeine Undo-Architektur, keine
automatische History-Kopplung in den Mesh-Mutationsmethoden selbst
(bleiben weiterhin History-unabhängig, §15 Punkt 5) — wie mit dem Nutzer
vor der Implementierung abgestimmt.

**Produktionscode-Änderungen:** `mesh.py` (`load_state()` neu,
`from_state()` refaktoriert, verhaltensgleich), `operations/topology.py`
(neu), `operations/__init__.py` (Export), `history.py` (Docstring-Korrektur).

### Architekturverträge (`test_core.py`)

Alle 11 Blöcke (AD-001 IDs, split, Query-API, connect, collapse ×2, AD-003 Lifecycle ×3, Selection, Serialisierung): **PASS**.

Invarianten-Checks wurden zusätzlich nach split/collapse/connect in `test_core.py` eingebunden.

## Fehler-Entscheidungsregel

Bei einem fehlgeschlagenen Test gilt:

1. **Test falsch?** — Erwartung widerspricht dokumentiertem Vertrag → Test anpassen.
2. **Core falsch?** — Vertrag klar, Implementierung verletzt ihn → Core fixen.
3. **Nicht spezifiziert?** — Keine Semantik erfinden; Test zurücknehmen oder als `skip` mit Verweis dokumentieren.

## Nächste Schritte (Plan §17, noch offen)

- Phase E: Serialisierung nach Mutationen (Roundtrip mit Allocator-Zustand)
