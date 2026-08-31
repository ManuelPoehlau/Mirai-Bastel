# Mirai-Bastel — V1 Core (Architekturvalidierung)

Dieser Code ist **kein produktiver Modeler**, sondern der minimale
Nachweis, dass die in V1_CORE.md / V1_SPEC.md festgelegten
Architekturentscheidungen (AD-001, AD-002, AD-003) tatsächlich tragen.
Umfang bewusst klein gehalten — Ziel war Architekturvalidierung, nicht
Feature-Menge.

## Was validiert wird

| Datei | Validiert |
|---|---|
| `ids.py` | AD-001: opake, monotone, nie wiederverwendete IDs |
| `mesh.py` | AD-002: geordnete Face-Boundary + Query-API statt interner Container; Mutation-Layer mit dokumentierter ID-Kontinuität pro Primitive (§7, §8) |
| `selection.py` | §3: Selection als eigener Domain-State, nicht Teil der History |
| `history.py` | §10, §15.5: generisches `Command`-Protocol statt `MeshOperation`-Kopplung |
| `operation.py` | AD-003: generischer `begin/update/commit/cancel`-Lifecycle, `target` statt hartcodiertem `mesh` |
| `operations/move.py` | konkrete Operation, die AD-003 tatsächlich durchspielt (inkl. Soft-Selection-Weight-Platzhalter) |
| `operations/transform.py` | WP-03 Transform-Foundation: gemeinsame Snapshot-/Commit-/Cancel-Basis + `RotateOperation`/`ScaleOperation` (fixer Pivot, inkrementelle update-Semantik) |
| `scene.py` | §12, §15.7: Scene als Hülle mit reservierten (leeren) Plätzen für `morph_targets`/`rig`/`animation` |
| `serialization.py` | §12: Scene-Hülle statt Mesh-only-Format, kollisionsfreie ID-Fortsetzung nach dem Laden |

## Ausführen

```bash
python3 -m tests.test_core
```

`tests/test_core.py` ist kein klassischer Feature-Test, sondern prüft je
Block **explizit einen Architekturvertrag** (z. B. "erzeugt update()
wirklich keinen History-Eintrag?", "bleibt die FaceId nach split_edge()
wirklich erhalten?").

## Bewusst NICHT enthalten (siehe V1_SPEC.md §16 / archivierte ADs)

- Generational Slotmap / ECS / Arena-Allocator
- volle Half-Edge-/Winged-Edge-Struktur
- Viewport, Rendering, echtes Event-System
- Deformation/Morph/Rig/Animation/Scripting/AI — nur die in AD-Runde 3
  beschriebenen Indirektionspunkte (Positions-API, ID-Kontinuität,
  generischer History-/Operation-Vertrag, Scene-Hülle) sind bereits
  vorhanden.
- Non-Manifold-Handling, Genus-Tracking
