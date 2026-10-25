# AD-REGIONS-01 — Face Regions (Saved Regions / Polygroups) Storage

**Status:** DECIDED ✓ (Manu, 2026-10-25), Slice 1 (Core storage) and Slice 2 (commands) implemented
**Gehört zu:** `docs/future_ideas/MODELING.md`, Priorität 1, „Gespeicherte Regionen / Polygroups“
**Grundlage:** AD-SYM-01 (gleiches Muster: vom Mesh besessener Wert), AD-001 (IDs nie wiederverwendet),
AD-021 §4.9 (ID-gebundene Daten gehören ins Mesh oder in eine mit ihm gesnapshottete Struktur, nicht in `Scene`),
`CORE_V1_FREEZE.md` §7 / §7.1.

**Frage:** Wo leben benannte, wiederverwendbare Face-Mengen (Brow, Upper Lip, Eyelids, Jaw), und was verspricht das System
bei Topologieänderungen?

## 1. Entscheidung

1. **Das Mesh besitzt die Regionen.** `Mesh.face_regions: FaceRegions | None` (`src/core/mesh.py`), ein unveränderlicher
   Wert aus `FaceRegion(name, faces: frozenset[FaceId])`, Namen eindeutig, Überlappung erlaubt, Reihenfolge = Anzeige.
   Kein Region = `None`, nie eine leere Instanz. Der Setter journalisiert den alten Wert wie `symmetry_definition`:
   `MeshChange.regions`, `MeshDelta.regions`, `end_change` / `rollback_change` / `revert_change` / `apply_delta`.
   Eine reine Regionen-Änderung ist ein nicht leeres Delta (sonst bucht `_mesh_transaction` sie nicht).
2. **Warum im Mesh:** derselbe Beweis wie AD-SYM-01 §1.1. Ein Speicherort außerhalb der Mesh-Snapshots
   (Application-Dict, Scene) desynchronisiert sich beim ersten Undo oder verlangt einen eigenen Command samt
   Selection-Mirror-Verdrahtung und ein `FORMAT_VERSION`-Sprung; im Mesh sind Undo/Redo, Rollback (Knife-Checkpoints) und
   die Szenendatei kostenlos. Der Core *besitzt* den Wert, er *kennt* keine Semantik (AD-SYM-01 §3).
3. **Datei:** additiver Schlüssel `"face_regions"` in `Mesh.export_state()` (Liste `{name, faces}`, IDs aufsteigend, `None`
   ohne Regionen), `load_state` liest mit `state.get`; keine `FORMAT_VERSION`-Erhöhung (Präzedenz `"symmetry"`).
4. **Nur Faces.** Vertices und Kanten einer Region werden abgeleitet (`mirai.regions`); damit bleibt die Region bei
   Topologieänderungen bedeutungsvoll und braucht keine eigenen Split-/Extrude-Regeln für Vertex-Mengen.
5. **Tote IDs bleiben im Wert.** Nur Leser filtern (`is_valid_face`). Ein Undo kann eine tote ID wieder lebendig machen;
   ein Prune beim Schreiben würde das verlieren (bekannte Schwäche von `HiddenSet`/`VertexMask`, die Sitzungszustand sind).
6. **Keine automatische Vererbung (Slice 1+2).** Der Core-Journal kennt nur Vorher-Zustände, keine Herkunft
   (`CORE_V1_FREEZE.md` §7.1 und ARCH-02 offen). Split, Connect, Knife, Dissolve und Extrude lassen Regionen unverändert; neue
   Faces gehören zu keiner Region, entfernte Faces verschwinden beim Lesen. Der Status meldet „N Faces durch Topologie-Edits
   verloren“. Eine generische Vererbungsregel aus dem Journal (neue Face erbt, wenn alle Kandidaten-Eltern in der Region
   sind) ist Slice 3 und braucht Hooks in `extrude.py` und `knife_resolve.py` sowie Manus Entscheidungen zu Dissolve über
   Regionsgrenzen und Extrude-Wänden. Sie ist ein Notbehelf für Face-Daten, keine Antwort auf ARCH-02.
7. **Links/Rechts wird abgeleitet,** nicht gespeichert: `SymmetryIndex.face_partner` / `expand_faces`. Zuweisen unter
   Symmetrie nimmt die Spiegelpartner mit (wie Hide und Mask).

## 2. Offene Punkte (Slice 3+)

Vererbung (s. o.), Mirror-Copy-Remap (neue ID-Räume), OBJ-Gruppen beim Import/Export, Anzeige auf der SubD-Fläche über
`face_parent`, Auswahl per Klick, Umbenennen (die App hat keine Texteingabe: Preset-Slots), ein Per-Face-Label-Layer, falls
das ganzwertige Journal (Messung: ~4 MiB und ~55 ms je Änderung bei einer 87k-Faces-Region) zu teuer wird.
