> **Status (2026-10-20):** Detailbericht zu Audit 1 (Stand 2026-10-19, `main` @ `435ac7e`). Discovery, keine Entscheidung. Kurzfassung für Manu: [ARCHITECTURE_AUDIT_2026-10-20.md](ARCHITECTURE_AUDIT_2026-10-20.md).
> **Überholt am selben Tag:** Die offenen Punkte E1 (`gl_PrimitiveID`: Flat ohne Flecken), E2 (Topologie-Operationen auf dem Referenz-PC) und E3 (Spike auf 87,5k) sind durch Manus Läufe beantwortet; siehe [Audit 2, §1](ARCHITECTURE_AUDIT_2026-10-20_FUTURE_REQUIREMENTS.md) und die Mess-Dokumente ([Spike-README](../../../experiments/gpu_picking_spike/README.md), [drag_cost-README](../../../experiments/drag_cost/README.md), [REFERENCE_HARDWARE](../../architecture/REFERENCE_HARDWARE.md)). Der Text unten wurde dafür **nicht** umgeschrieben. Eigene Container-Messungen: `experiments/architecture_audit_probes/` (`probe_mesh_cost.py`, `probe_morph_blend.py`).

# Mirai-Bastel — Viewport-, Mesh- und Workspace-Audit

**Modus:** Discovery. Es wurde nichts im Repository geändert, kein Branch, kein Commit.
**Stand:** `main` @ `435ac7e` (2026-10-19), Arbeitsbaum sauber. Seit dem GPU-Spike (`75448c4`) gibt es **keine** Änderung an `src/`, `experiments/`, `tests/` oder `playground/` (geprüft mit `git diff --stat 75448c4 HEAD`), nur `docs/future_ideas/`. Die in AD-022/AD-023 genannten Befunde gelten also unverändert für den heutigen Code.
**Quellen:** AGENTS.md, CLAUDE.md, die im Auftrag genannten Dokumente, der Code unter `src/`, plus Manus Referenz-PC-Lauf des GPU-Spikes (Anhang).
**Kennzeichnung:** **[RPC]** = auf dem Referenz-PC gemessen (Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3.0, Python 3.14.2). **[C]** = Container (Xeon 2,1 GHz, Python 3.13, llvmpipe, nicht übertragbar, Faustregel RPC ≈ 2× langsamer bei Python-Code, REFERENCE_HARDWARE §2). **[H]** = Hypothese/Schätzung.

---

## 1. Executive Verdict

**Ein großer Neuentwurf ist durch die vorliegende Evidenz nicht gerechtfertigt. Die stärkere Hypothese ist ein selektiver Umbau (Option B), dessen erste Schritte wie Option A aussehen und ohne Core-Änderung auskommen.**

Die Begründung in fünf Punkten:

1. **Der Viewport-Umbau hat funktioniert.** Dirty-State, persistente GPU-Ressourcen und Positions-Patching sind Produktionscode. Navigation ist auf dem Referenz-PC flüssig, auch mit 87 500 V (Draw 1,19 ms/Schritt, GPU 0,56 ms **[RPC]**, REFERENCE_HARDWARE §2). Der Draw ist nicht der Engpass.
2. **Der verbleibende Picking-Engpass ist auf dem Referenz-PC jetzt belegt gelöst, im Spike.** Auf `gollum_20k` fällt der Pick nach einem Orbit von 160,9 ms auf 3,3 ms (49×), der Hover bei gültigem Zustand von 18,6 auf 1,65 ms, Box 300 px von 2 384 auf 89 ms **[RPC]**. Das ist kein Argument für eine neue Mesh- oder Viewport-Architektur, sondern für den ersten Teil von Option B.
3. **Der größte noch offene Engpass ist nicht das Picking, sondern die Topologie-Operation samt Undo.** Eine Operation kostet auf `gollum_20k` 0,8–1,8 s, ein Undo ~1 s **[C]** (AD-023 §1). Die Operation selbst dauert 1–74 ms, der Rest ist Ganz-Mesh-Arbeit in reinem Python: Snapshots, Triangulation, Normalen, Buffer. **Eine andere Datenstruktur (Half-Edge, BMesh-artig) löst genau diese Posten nicht.** Das ist der wichtigste Befund dieses Audits.
4. **Das heutige Mesh hat konkrete, aber begrenzte Schwächen** (§4): kein Änderungsprotokoll und keine Revision, `vertex_edges` ist O(E), Adjazenz ist dreifach dupliziert, die History hält Ganz-Mesh-Snapshots ohne Obergrenze. Sie lassen sich hinter der unveränderten Query-API beheben (AD-002 hält das ausdrücklich offen).
5. **Für die künftigen Workspaces ist die größere offene Frage die Auswertung von Deformationen** (Morph/Skin-Vorschau in reinem Python ohne NumPy), nicht die Mesh-Topologie. Das ist eine Architekturfrage, die vor Morph/Skin-Räumen entschieden werden muss, aber heute noch nicht dringend ist (§6).

Ehrliche Einschränkung: Die Topologie-Zahlen sind nur im Container gemessen. Ob die Python-seitige inkrementelle Arbeit auf dem Referenz-PC in den Zehn-Millisekunden-Bereich kommt, ist **[H]**. Genau das ist der Entscheidungspunkt zwischen B und C (§10).

---

## 2. Architektur-Landkarte (Ist-Zustand)

```
src/core/        FROZEN V1 (CORE_V1_FREEZE.md §1, §7.1 Ausnahmen)
  mesh.py          Mesh: dict[Id,_Data]; Face = geordnete Boundary-Liste; Edge = (v0,v1,faces[])
  history.py       HistoryStack: linearer Command-Stack, Protokoll undo/redo (kennt Mesh nicht)
  operations/topology.py  MeshStateCommand: Ganz-Mesh-Snapshots vorher/nachher (:36)
  scene.py         Scene: Objekte (ObjectId -> SceneObject{mesh,transform,pivot,state}),
                   edit_object_id, 1 Selection, 1 HistoryStack; morph_targets/rig/animation = None (:160-164)
src/mirai/       Application (3 851 Z., 159 Methoden) + interaction/ + topology/ (Tools) + viewport/ (Kamera, Picker)
  application.py   Einziger Besitzer von PickCache; _mesh_transaction (:3253) = die Commit-Grenze
  viewport/picking.py, picking_cache.py, box_select.py   CPU-Picker (Bildschirmraum)
src/viewport/    unabhaengig von mirai (Daten fliessen Core -> Viewport)
  viewport.py      Viewport: 1 Edit-RenderMesh + object_entries (weitere RenderMeshes) + Surface-Provider (H7)
  render_mesh.py   RenderMesh: DirtyState -> sync() -> ResourceStore (Positions-Patch oder Strukturneubau)
  derived.py       Normalen, Bounds, vertex_to_faces
  gl_render_store.py   EIN indizierter VertexList je RenderMesh; Shader nutzt gl_PrimitiveID (:254)
```

Verifizierte Eigenschaften:

- **Die Query-API ist wirklich dicht.** Kein Zugriff auf `_vertices/_edges/_faces/_edge_lookup` außerhalb von `mesh.py` (grep über `src/`). Das ist die Voraussetzung dafür, dass die interne Darstellung austauschbar wäre (AD-002, `mesh.py:5-8`).
- **Alle Schreibzugriffe auf die Container liegen in einer Datei**, in ~35 Stellen in `mesh.py` (grep), verteilt auf ~10 Primitive (`add_vertex`, `add_face`, `remove_face`, `split_edge`, `collapse_edge`, `split_face`, `dissolve_*`, `delete_*`, `load_state`).
- **Der Viewport ist kein Ein-Mesh-Renderer**, sondern ein Kompositor mehrerer `RenderMesh`-Einträge: Edit-Objekt mit Overlays, beliebig viele Objekt-Einträge (Referenzen, Ghost, Modellmatrix je Eintrag, `viewport.py:257-336`) und eine Ersatzfläche (H7, `:389-470`, nur Anzeige, ein Provider, AD-013 H7-R1…R4).
- **Es gibt keinen Workspace-Begriff im Code** (`grep -rniE "workspace|room" src` ist leer). Es gibt nur Selektionsmodi 1/2/3/4 und Input-Kontexte (`bindings.py`, z. B. `subd_lab`, `morph_lab`). Retopo kommt in `src/` nicht vor.

---

## 3. Evidenzregister

| Befund | Status | Quelle |
|---|---|---|
| V1 verbrachte ~95 % der Interaktionszeit in Rebuilds/Normalen | gemessen, historisch, behoben | VIEWPORT_V02_ARCHITECTURE §1; `render_mesh.py:347-406` |
| Orbit/Pan/Zoom-Draw flüssig, 87,5k navigierbar | **[RPC]** gemessen / subjektiv | REFERENCE_HARDWARE §2 |
| Vor den Fix-Slices: Zoom 1,66 s, Hover 252 ms, Klick 571 ms auf gollum_20k | **[RPC]** gemessen, **überholt** durch Slice 1+2 | drag_cost README :387 |
| Slice 1+2 (nearest-first, Projektor, Face-Grid, Hover-Koaleszenz) | gebaut, durch Äquivalenztests belegt; Zahlen nur **[C]** | drag_cost README :554-706, `tests/test_picking_equivalence.py` |
| CPU-Picker heute auf gollum_20k: nach Orbit 160,9 ms, Hover 18,6 ms, Box 300 px 2 384 ms | **[RPC]**, neu (Spike-Spalte "cpu") | Manus Anhang |
| GPU-ID-Picking: nach Orbit 3,3 ms, Hover 1,65 ms, Box 300 px 89 ms; ID-Render 1,14 ms GPU-Zeit | **[RPC]**, neu | Manus Anhang |
| GPU-Treffer-Übereinstimmung mit CPU: Vertex 97,7 % (Tiefe 98,7 %), Edge 96,3 %, Face 86,7 % + 13,2 % Halb-Pixel | **[RPC]**, neu; Abweichungen = Nachbarelement im selben Pixel | Manus Anhang |
| AD-022 / AD-023 | **PROPOSED**, keine Entscheidung | beide ADs, Kopfzeile |
| Topologie-Op 0,8–1,8 s, Undo ~1 s auf gollum_20k | nur **[C]**; auf RPC **nicht gemessen** | AD-023 §1 |
| `export_state` 121/601 ms, `load_state` 248/2 087 ms (21,9k/87,5k) | **[C]**, von mir nachgemessen, deckt sich mit AD-023 (84/660, 311/2 139) | `probe_mesh_cost.py` |
| `gl_PrimitiveID` zuverlässig auf dem Referenz-PC | **offen** (B3c-Verdikt "pending") | WP-06_INTAKE_LOG :86, REFERENCE_HARDWARE §2 |
| GPU-Spike auf 87,5k, Flat-Shading-Check | **fehlen** im Anhang (Schritte 3 und 4 des "Praktischen Tests") | gpu_picking_spike README :111-120 |
| Ziel-Größe für *Bearbeitung* (20k? 87,5k?) | **offen, Artist-Entscheidung** | drag_cost README :551, ATELIER D1c |
| Soft+Symmetrie am Body über 8 ms (p95 8,6–15,9) | **[RPC]**, offen | REFERENCE_HARDWARE §2 |
| `CORE_API_AUDIT.md` (Aug 2026) | **teilweise veraltet**: "kein `t` bei `split_edge`" stimmt nicht mehr (`mesh.py:281`); vor `Scene`/`ObjectId` geschrieben; nur Quelltext-Analyse | CORE_API_AUDIT |
| AD-022 §2 "ID-Render auf 9800 GTX ~1–3 ms, nicht gemessen" | **jetzt gemessen**: 1,14 ms (GL-Timer), 1,43 ms Wandzeit **[RPC]** | Anhang |
| V02 §5.4: "Viewport erkennt `topology_revision`-Änderung" | **so nicht umgesetzt**: Mesh hat keine Revision, der Aufrufer meldet manuell (§4) | `picking_cache.py:14-18`; `application.py` |
| V1_CORE §19 Frage 1 "Winged vs Half-Edge" | formal offen, praktisch entschieden: "bewusst nicht Teil des Freeze" | CORE_V1_FREEZE §4 |

---

## 4. Mesh-Architektur

### 4.1 Stärken (erhalten)

- **Stabile, monoton vergebene IDs, nie wiederverwendet** (AD-001, `ids.py`). `load_state` setzt Zähler nur vorwärts (`mesh.py:1111`). Damit sind `(ObjectId, VertexId)`-Bindungen "gültig oder tot, nie falsch" (AD-021 §4.9). Das ist die Grundlage für Morph, Skin, Symmetrie.
- **Quads/n-Gons als Boundary-Liste** (`_FaceData.boundary`). Passt zu Quad-Modellierung, SubD und Retopo.
- **Dichte Query-API** und dokumentierter ID-Kontinuitätsvertrag je Mutation.
- **Invarianten-Test** (`tests/mesh_invariants.py`) und Identitäts-Kontinuitätstests.
- **Symmetrie-Definition liegt im Mesh** und reist durch Snapshot/Undo (AD-SYM-01), ein Präzedenzfall für ID-gebundene Daten.

### 4.2 Konkrete Schwächen

| # | Schwäche | Beleg | Wirkung |
|---|---|---|---|
| S1 | `vertex_edges` ist O(E) | `mesh.py:179-182`; 2,5 ms/Aufruf bei 21,9k, 10,7 ms bei 87,5k **[C]**; 19 Aufrufstellen in `src/` | Knife, Loop/Ring, Dissolve; `influence.py:120` umgeht es bereits mit einem Sammeldurchlauf |
| S2 | Adjazenz mehrfach dupliziert | `DerivedGeometry.vertex_to_faces` (`derived.py:262`), `PickCache.vertex_faces` (`picking_cache.py:120`), plus `edge_faces`-Listen im Core | je Topologie-Änderung mehrfach komplett neu aufgebaut |
| S3 | **Keine Revision und kein Änderungsprotokoll** | kein Zähler in `mesh.py`; `picking_cache.py:14-18` sagt es ausdrücklich; 14× `_pick_cache.invalidate()`, 4× `on_topology_changed`, 6× `on_vertices_moved` in `application.py` | Caches werden von Hand invalidiert; mit mehreren Hosts/Workspaces auf demselben Mesh fehleranfällig. **Es fehlt auch die Information, *welche* Elemente sich änderten**, und genau die brauchen AD-023 H1/V0/V1 |
| S4 | History = Ganz-Mesh-Snapshots, ohne Obergrenze | `topology.py:36-53`; `history.py` ohne Limit; `_mesh_transaction` macht 2× `export_state` plus Dict-Vergleich (`application.py:3273-3281`) | Speicher: ein Snapshot ≈ 31 MB (21,9k) bzw. 123 MB (87,5k), **ein Undo-Schritt ≈ 61 / 246 MB** **[C]**, tracemalloc, von mir gemessen. 30 Schritte auf 20k ≈ 1,8 GB **[H]** (Achtung: 8 GB RAM im Referenz-PC) |
| S5 | Snapshots dienen auch als Transaktions-Rollback | `export_state`/`load_state` in `knife.py:239/751`, `extrude.py:165/330`, `symmetric_knife.py:575`, `delete_dissolve.py:84-90`, `connect*.py`, `application.py:1227,1907` | Delta-History (AD-023 H1) allein beseitigt das Muster nicht: jede dieser Stellen bräuchte denselben Mechanismus |
| S6 | Keine Ecken-/Radial-Navigation (kein "nächste Kante um den Vertex") | API-Liste `mesh.py:157-190` | Loop/Ring, SubD-Pole, Retopo-Strip-Tools müssen aus `vertex_edges` + Geometrie rekonstruieren. Eine **konkrete** Einschränkung, die Half-Edge lösen würde |
| S7 | Nicht-Mannigfaltigkeit wird nicht im Core erzwungen | `add_face` (`mesh.py:215`) prüft `faces ≤ 2` nicht; nur der Test (`mesh_invariants.py`) tut es; CORE_API_AUDIT :484 warnt vor Skin-Gewichten auf solcher Geometrie | latent, heute durch die Tools abgesichert |
| S8 | Puffer-Zeilen ≠ IDs, Tabelle wird jedes Mal komplett neu gebaut | `render_mesh.py:176-192` (`_vertex_index`, `_face_row` per Enumeration) | harmlos heute; **blockiert inkrementelles Patchen und GPU-ID-Pass**, bis eine stabile Zeilentabelle (mit Freiliste) existiert |
| S9 | Reines Python, kein NumPy | Suche in `src/`: kein `import numpy`; V02-Research §19 | Kostenfaktor für alles O(V); NumPy-Verfügbarkeit auf dem Q9550 (SSE4.1, kein SSE4.2/AVX) ist **ungeprüft** (REFERENCE_HARDWARE §2) |
| S10 | Speicher pro Vertex ≈ 1,7 KB (Mesh+Szene, Python-Objekte) | 38 MB bei 21,9k, 152 MB bei 87,5k **[C]**, tracemalloc, obere Schätzung | für ein einzelnes Mesh unkritisch, vervielfacht sich über Snapshots (S4) |

### 4.3 Alternativen

| | Komplexität (Nachbarschaft/Op) | Speicher (reines Python) | Risiko / Migration | Undo-/ID-Korrektheit | Löst S1–S10 |
|---|---|---|---|---|---|
| **1. Beibehalten** | S1 O(E) bleibt | wie heute | null | unverändert | nichts |
| **2. Gezielte Index-/Revisionsstrukturen im Mesh** (Vertex→Kanten, Vertex→Faces inkrementell gepflegt; Revisionszähler; Änderungsjournal der berührten Elemente) | O(1) für S1; Journal O(1) je Primitiv | +2 Dict-Ebenen | **niedrig–mittel**: nur `mesh.py` intern, Query-API bleibt; braucht Freeze-Ausnahme nach §7 (interne Änderung, kein neuer Vertrag) | Journal liefert die "touched sets" für Delta-Undo, ohne dass jedes Tool sie melden muss (AD-023 §4: "größte Code-Oberfläche") | S1, S2, S3, Voraussetzung für S4/S5/S8 |
| **3. Hybrid: editierbares Mesh authoritativ, abgeleitete Darstellungen je Aufgabe** | wie 2 | +Ableitungen | niedrig, **teilweise schon Praxis**: `RenderMesh`, `PickCache`, SubD (`subd.py`, eigene Topologie je Level), Morph-Fläche (`morph.py`) sind abgeleitet; fehlt nur ein gemeinsamer Revisions-/Journal-Vertrag | abgeleitete Daten sind nie Wahrheit, History bleibt am Mesh | S3, S8; formalisiert, was existiert |
| **4. Half-Edge / Winged-Edge / BMesh-artig** | O(1) geordnete Ecken- und Radial-Navigation | **höher**: ~4 Python-Objekte je Quad | **hoch**: neue Implementierung hinter der Query-API (alle Tools unter `src/mirai/topology/` (17 Dateien) lesen nur die API, das ist technisch machbar), aber Freeze §4 schließt sie "bewusst" aus; jede ID-Kontinuitäts-Aussage je Mutation muss neu bewiesen werden | Undo/ID-Tests müssen komplett neu bestätigt werden | **nur S6 (und S1)**. Löst S4, S5, S8, S9 nicht, genau die Posten, die 80–95 % der Topologie-Op-Zeit ausmachen |

**BMesh als Referenz:** Aus Blender lässt sich lernen (extern, nicht in diesem Repo geprüft): (a) **Attribut-Layer je Element** statt externer Dicts (Gewichte/Morph-Deltas leben am Mesh, passt zu AD-021 §4.9 und dem `"symmetry"`-Schlüssel), (b) **GPU-Select-Puffer fürs Picken** (entspricht AD-022 B), (c) Blender macht Edit-Mode-Undo meines Wissens ebenfalls mit Mesh-Kopien, die Geschwindigkeit kommt aus C und nicht aus der Datenstruktur. Das letzte ist eine Erinnerung und gehört vor einer Entscheidung geprüft. Der Gollum-Vergleich von Manu ("in Blender sehr flüssig") sagt daher wenig über die richtige Datenstruktur.

**Empfehlung zu Audit A:** Option 2 (als Teil von 3). Eine Umstellung auf Option 4 ist erst gerechtfertigt, wenn S6 (Ecken-Navigation) für ein konkretes Feature nachweislich nicht aus `vertex_edges` + Geometrie lösbar ist. Der Auslöser dafür wäre ein Retopo-Strip-Tool oder SubD-Pole-Handling. Die Query-API macht diesen Schritt später möglich, falls nötig (AD-002), er wird durch Option 2 nicht verbaut.

---

## 5. Viewport-Engpässe

### 5.1 Datenfluss heute

```
Tool/Op -> Application._mesh_transaction (:3253): export_state x2 + Dict-Vergleich
        -> history.push(MeshStateCommand)
        -> topology? Viewport.on_topology_changed -> RenderMesh._sync_topology (:347):
             full_recompute (Adjazenz+alle Normalen) + Neu-Triangulierung aller Faces
             + _rebuild_resources (alle Puffer, VertexList neu) + PickCache.invalidate
        -> nur Positionen? on_vertices_moved -> _sync_geometry (:355): 1-Ring-Normalen, Positions-Patch
        -> _refresh_hover -> PickCache.refresh (O(V+F) je Kamerazustand, picking_cache.py:80)
```

### 5.2 Bereits behoben (belegt)

- Strukturneubau bei Kamera/Selektion/Positionsänderung. Nur bei Topologie noch (Dirty-State, `render_mesh.py:316-346`).
- W-Drag: Positions-/Normalen-/Face-Zeilen-Patch (`render_mesh.py:355-405`); Bounds lazy; ≤ 8 ms p95 bis Body **[RPC]**.
- CPU-Picking: nearest-first, Projektor, Face-Grid, Hover-Koaleszenz. Box 300 px vertex gollum_20k 19 006 → 312 ms **[C]** (drag_cost :654); Äquivalenz durch Tests belegt.

### 5.3 Was bleibt, und warum

| Interaktion | Rest-Ursache | Wächst mit | Von AD-022? | Von AD-023? |
|---|---|---|---|---|
| Zoom / erster Pick nach Kamerawechsel | `PickCache.refresh` projiziert alle V+F je Kamerazustand | V+F | **ja** (RPC: 161 → 3,3 ms) | nein |
| Hover/Klick gültiger Cache | O(V)/O(E)-Scan | V,E | ja (18,6 → 1,65 ms RPC) | nein |
| Box/Paint | ein Test je Element | Elemente in Box | ja (2 384 → 89 ms RPC); die Variante "ids" verliert ~9 % bei 300 px Edge (11 315 vs 12 455), die Tiefen-Variante liegt bei +3 % / −0,7 % | nein |
| **Topologie-Op + Undo** | 3 Ganz-Mesh-Pässe (S4) + Neu-Triangulierung + Normalen + Puffer | V+F, jede Op | **nein** (5–10 % Picking) | **ja** |
| Extrude: 2 Strukturneubauten je Geste (**Korrektur**: der Bericht nannte 3; AD-023-Review B-1) | begin, release; dazwischen nur Vertex-Patch | V+F | nein | ja (V2) |
| Große Soft-/Symmetrie-Drags | `store.update` je Vertex | bewegte V | nein | teilweise |
| Edit-Objekt-Wechsel (2,6–3,0 s), Objekt hinzufügen (6,8 s), Objekt-Pick (0,8 s) auf 20k **[C]** | `Viewport.set_edit_mesh` baut neuen `RenderMesh` (`viewport.py:336`) | V+F | nein | ja (Eintragscache) |
| SubD-Level 2 Drag-Schritt 148 ms, Level 3 2 845 ms (Head) **[C]** | 1,64 von 1,80 s in `GLRenderStore._patch_attribute` (schreibt ganzen Puffer) | abgeleitete V | nein | betrifft V1-Patch-Vertrag |

### 5.4 Was der Spike auf dem Referenz-PC beweist, und was nicht

**Beweist [RPC]:** FBO + `glReadPixels` laufen auf dem GL-3.3-Legacy-Treiber ohne Fehler; der GL-Timer funktioniert; Kamerawechsel-Kosten im Python-Code verschwinden (Pick nach Orbit 3,3 ms Vertex / 3,75 Edge / 2,4 Face). Die Erwartung aus AD-022 ("~1–3 ms") ist bestätigt. Bei Head/Body ist GPU-Hover nicht schneller als CPU (Head 0,85 vs 0,21 ms), das ist irrelevant, beides unter einem Frame.

**Beweist nicht:**
- **87,5k** (Schritt 3 des Praktischen Tests fehlt). Die Tendenz aus dem Container (Box 6,9 s → 78–92 ms, Übereinstimmung 79–91 %) ist plausibel, aber keine RPC-Zahl.
- **`gl_PrimitiveID`** (Schritt 4). Der Spike vermeidet es bewusst (B1, eigene Puffer). Die Entscheidung B1 vs B2 hängt daran. Der Spike lief mit 795 ms Aufbau je Mesh-Zustand in Python (B1), unbrauchbar für Bearbeitung, solange B1 gewählt ist.
- Knife, Paint, Objekt-Pick, Snapping, platzierte Objekte, Resize, W-Drag (AD-022 §2 "Not covered").
- Die Ursache der 89 ms Box 300 px: vermutlich Lesen und Python-Dekodieren der Pixel **[H]**, nicht analysiert.
- p95 und Ausreißer: nur p50 mit 15 Stichproben (versteckte 1024×768-Fenster).

**Offene Korrektheitsfragen** (AD-022 §4, nicht vermeidbar in jeder GPU-Variante): Silhouetten/streifende Winkel, Pixel-Zentrum vs. -Ecke (13 % der Face-Cursor auf Rändern), Sub-Pixel-Dichte. Das ist eine **Artist-Prüfung**, kein Beweisproblem.

### 5.5 Wechselwirkung AD-022 ↔ AD-023 (müssen gemeinsam entschieden werden)

1. **Zeilentabelle (S8).** B2 zeichnet die ID-Pässe aus den `RenderMesh`-Puffern: Face-ID über `triangle_faces`, plus neuen Edge-Index-Puffer und Punkt-Draw. AD-023 V1 patcht dieselben Puffer inkrementell. Beide brauchen dieselbe **stabile ID→Zeile-Zuordnung mit Freiliste**. Wer sie zuerst baut, legt sie für den anderen fest.
2. **Berührte Elemente.** V0/V1 (Viewport) und H1 (History) brauchen die Menge der geänderten Elemente. Ein Journal im Mesh (Option 2) liefert sie für beide.
3. **Reihenfolge im Frame.** Der ID-Pass muss nach `sync()` rendern; nach Topologie-Änderung und Undo gilt das für Hover-Neupick.
4. **PickCache bleibt** für headless, Tests und die exakte Knife-Mathematik (AD-022 §5). Seine Neuaufbau-Kosten (P in AD-023) bleiben dort relevant.
5. **B1 verdoppelt den W-Drag-Patchaufwand**, B2 nicht, aber B2 hängt an `gl_PrimitiveID`.

---

## 6. Workspace-Vorschlag

**Leitidee:** Ein Workspace ist **keine eigene Anwendung und kein eigener Renderer**, sondern eine *Konfiguration* über einem gemeinsamen Kern: welche Objekte in welcher Rolle sichtbar sind, welche Werkzeuge/Binding-Kontexte aktiv sind, welche Selektionsdomänen und Overlays gelten, was gepickt werden darf. Der Code hat dafür schon die Bausteine (Edit-Objekt vs. Referenz, Ghost-Anzeige, Input-Kontexte, H7-Ersatzfläche). Es fehlt der benannte Rahmen, der sie bündelt.

**Gemeinsame Dienste (existieren):** Mehr-Eintrags-Viewport, Kamera, `Scene` mit Objekten und einer History für alle (`HistoryStack` kennt nur das Command-Protokoll), Szenendatei Format v2, Symmetrie im Mesh, Selektion/Soft-Selection, Picker (CPU, künftig GPU).
**Gemeinsame Dienste (fehlen):** ein Picking-Dienst mit einer Schnittstelle und zwei Implementierungen; ein Provider-*Liste* statt eines Providers (H7-R4); stabile Zeilentabelle; Eintragscache beim Edit-Objekt-Wechsel; ein Auswertungsort für Deformationen.

| Raum | besitzt / ändert | referenziert | Werkzeuge & Regeln | eigener Renderer? | Zustand beim Wechsel |
|---|---|---|---|---|---|
| **Model** | Mesh (Topologie, Positionen, Symmetrie) | Referenzen | alles heutige; SubD als Anzeige (H7) | nein, ist der Kern | Kamera, Edit-Objekt, Selektion, History |
| **Morph** | Morph-Ziel-Deltas (ID-gebunden an die Basis) | Basis-Mesh | Gewicht, Vergleich, Relativ/Absolut; Basis-Topologie darf sich nicht ändern (ARCH-02) | nein: zweites Objekt + Ersatzfläche (belegt im Morph Lab, KEEP) | Gewicht ist reine Ansicht (Manu: nicht gespeichert) |
| **Retopo** | *neues* Mesh, unabhängige Topologie (eigener ID-Raum) | Quellfläche als Referenz (statisch, evtl. 87,5k+) | Snapping/Projektion auf die Quelle, Strip-Werkzeuge | nein; **aber** ein Treffer-Dienst auf der Referenz | Zuordnung Retopo↔Quelle |
| **Rig** | `Scene.rig` (szenenweit, AD-021 §4.9) | Objekte | Gelenke/Controls; **neue Zeichen- und Pick-Primitive** (Linien/Punkte-Overlays existieren) | nein, Overlay-Schicht | Rig-Auswahl |
| **Skinning** | Gewichte, Schlüssel `(ObjectId, VertexId)` | Rig, Mesh | Paint (vorhanden), Gewichts-Farbanzeige (**Vertex-Attribut fehlt**), Deformationsvorschau | nein, aber braucht Auswertungsort | Gewichtsansicht |
| **Animation** | `Scene.animation` | alles | Zeit, Keys auf `transform`/`state` je ObjectId | später | später |

Zu den beiden besonderen Fragen:

- **Morph und Basis-Mesh.** Das Lab hält das Ziel als ID-identische Mesh-Kopie (`Mesh.from_state(base.export_state())`) und paart über gleiche VertexIds, gesichert über eine `topology_signature`. Das ist eine Laborkonvention, kein Format (Lab-README :175). Produktions-Heimat laut AD-021 §4.9: am Mesh oder in einer mit ihm gesnapshotteten Struktur, **nicht** in `Scene`. Die Entscheidung ist ausdrücklich vertagt. Ändert sich die Topologie, schaltet das Lab den Morph ab. Das ist die Regel "nie stillschweigend falsche Korrespondenzen" (future_ideas/ANIMATION.md) und der Kern von ARCH-02.
- **Retopo und zwei Flächen.** Die Quelle ist eine *statische* Referenz. Das ist das einzige Szenario, in dem ein kamerauabhängiger Index sich sichtbar auszahlt: Ein BVH-Aufbau (0,65 s bei 21,9k, 3,2 s bei 87,5k in reinem Python **[C]**) geschieht einmal je Referenz, die Abfrage kostet ~0,07 ms (drag_cost README, "Audit at HEAD", What-if-Tabelle). Mit dem heutigen CPU-Pfad kostet ein Snap 2 / 8 ms bei gültigem Cache, plus 107 / 526 ms nach jedem Kamerawechsel, und k Snaps je Mausbewegung kosten k-mal. **GPU-Picking (ID+Tiefe) liefert nur den Treffer entlang des Sichtstrahls**; "nächster Oberflächenpunkt" ist damit nicht abgedeckt (drag_cost README, "Retopology snapping on the current architecture"). Die beiden AD-022-Optionen A und B schließen sich also für Retopo **nicht** aus: GPU für die Auswahl am Edit-Mesh, statischer Index für die Referenz. Das ist eine Entscheidung, die erst fällt, wenn Retopo ein Arbeitspaket ist (ebd.).

**Wann ein eigener Modus, wann eine eigene Ansicht, wann ein eigener Viewport?**
Modus/Konfiguration reicht für Model, Morph, Retopo, Rig, Skinning. Eine zusätzliche *Ansicht* (zweite Kamera auf dasselbe Szenen-Objekt, z. B. Quelle neben Retopo-Mesh oder Basis neben Morph-Ziel) wird erst gebraucht, wenn der Artist sie fordert; das Morph Lab löst "nebeneinander" heute mit räumlichem Versatz (+X 1,25 Breiten). Ein eigener Viewport-Code ist für keinen Raum durch die Evidenz begründet.

**Zwei Warnungen aus dem Code:**
1. **Raumwechsel ist heute O(Mesh).** `set_edit_mesh` baut den `RenderMesh` neu (`viewport.py:336`); gemessen 2,6–3,0 s auf 20k **[C]**. Ein Wechsel Model↔Retopo wäre damit zäh, bis Einträge gecacht werden.
2. **Deformationsvorschau in reinem Python skaliert nicht.** Morph-Gewichtsschritt: 24,7 ms auf 928 V mit allen Punkten verschieden **[C]** (Lab-README :157-168); linear auf 20k extrapoliert ≈ 0,5 s **[H]**, auf dem Referenz-PC ≈ 1 s **[H]**. Ein Gewichtsregler (J-4) und Skinning-Vorschau brauchen deshalb einen anderen Auswertungsort (Vertex-Shader mit Delta-/Gewichts-Attributen, reicht in GL 3.3, oder NumPy, falls auf dem Q9550 lauffähig). Das ist eine Entscheidung, bevor Morph/Skin produktiv werden, **nicht jetzt**.

---

## 7. Optionen im Vergleich

| | **A — Inkrementell** | **B — Selektiv umbauen** | **C — Großer Neuentwurf** |
|---|---|---|---|
| Inhalt | GPU-Picking (AD-022) wie vorgeschlagen; H0, V0, V2 aus AD-023 (kein Core-Eingriff); Messung der Rest-Engpässe | A **plus** Mesh-Journal/Revision + O(1)-Adjazenz im Mesh (Freeze-Ausnahme), Delta-History (H1), stabile Zeilentabelle + inkrementelle Puffer (V1), Picking-Dienst, Workspace-Rahmen mit Provider-Liste und Eintragscache | Half-Edge/BMesh-Kern, neue Mesh-Repräsentation (evtl. Arrays), neuer Renderpfad |
| Nutzen (Evidenz) | Picking: 49× nach Orbit, 27× Box **[RPC]**. H0 spart einen von drei Ganz-Mesh-Pässen (~84 ms/21,9k **[C]**) | zusätzlich: Topologie-Op und Undo von ~1 s auf ms-Bereich (AD-023-**Schätzung**, nicht gemessen) | löst S6 und lässt Arrays zu; **keine** Messung zeigt, dass es die Topologie-Op-Kosten löst |
| Grenzen | Topologie-Op bleibt bei ~0,5 s+ (H0/V0 ~2× **[H]**); Speicherwachstum der Snapshots bleibt | Python-Rest-Arbeit auf dem Q9550 offen **[H]** | alles offen |
| Behalten | alles | alles Getestete: Tools, API, IDs, Szenenformat, Viewport-Dirty-State | wenig; Tools müssten gegen neue API re-validiert werden |
| Risiko | gering; Picker-Divergenz CPU/GPU | **mittel**: falsches Delta korrupt das Undo still (AD-023 §4), braucht Debug-Modus "Delta == Snapshot" | **hoch**; Freeze §4 schließt es aus; Regressionen in allen validierten Tools |
| Aufwand / Pflege | klein | mittel; neue Pflichtschnittstelle (Journal) für Core-Primitive | groß; laufende Doppelpflege während der Migration |
| Entscheidungstor | AD-022 durch Manu + Review; Flat-Check + 87,5k-Lauf | AD-023-Spike (§10) zeigt ms-Bereich auf RPC | A/B reichen nach Spike *nicht*, und ein konkretes Feature scheitert nachweislich an S6 oder am Python-Speed |
| Spricht dafür | Manus Priorität "GPU-Picking größter Gewinn" | Manus Priorität "inkrementelle Topologie gleich wichtig" + Workspaces | nur ein Messergebnis, das B widerlegt |

A und B sind keine Gegensätze: B ist A, ergänzt um Core-interne Arbeit, die erst nach dem Spike-Ergebnis freigegeben wird.

---

## 8. Migrationsstrategie (reversibel, Gates)

Keine Backlog-Liste, nur die Reihenfolge der Entscheidungen:

1. **Messen, nichts bauen** (Gate 0): Referenz-PC-Läufe aus §10; AD-022 Review.
2. **AD-Entscheidungen** (Gate 1): AD-022 und AD-023 *gemeinsam* entscheiden (§5.5), nicht nacheinander.
3. **Ohne Core-Änderung zuerst** (Gate 2): H0 (Snapshot lazy), V0 (Triangulierung/Normalen pro Face cachen), V2 (ein Sync je Geste), GPU-Picking hinter Schalter für Hover/Klick. Jeweils mit Äquivalenztest "inkrementell == Vollneubau", wie bei Slice 1+2.
4. **Core-Ausnahme erst nach Spike-Ergebnis** (Gate 3): Journal/Revision, dann H1 mit Debug-Vergleich gegen Snapshot. Alle `export_state`-Rollback-Stellen (S5) auf denselben Mechanismus.
5. **Workspace-Rahmen** (Gate 4): zuerst Provider-Liste (H7-R4 verlangt Review), dann Eintragscache für den Edit-Objekt-Wechsel; Deformations-Auswertungsort entscheiden, bevor Morph/Skin produktiv werden.
6. **Erhalten, was gilt:** Query-API, stabile IDs, Undo-Semantik, Szenenformat v2 (Versionierung statt Bruch), alle Tests unter `tests/`. Rückfall je Schritt: Schalter bzw. alter Pfad bleibt, bis der Äquivalenztest grün und Manus Praxis-Check erfolgt ist.

---

## 9. Offene Fragen

**Engineering (nicht aus dem Repo beantwortbar):**
- E1: Liefert der Treiber `gl_PrimitiveID` zuverlässig? (entscheidet B1 vs B2)
- E2: Wie schnell sind Topologie-Op und Undo auf dem Referenz-PC? (nur Container-Zahlen vorhanden)
- E3: Spike auf 87,5k auf dem Referenz-PC; p95/Ausreißer.
- E4: Läuft NumPy auf dem Q9550 (SSE4.1, kein SSE4.2/AVX)? REFERENCE_HARDWARE nennt das als zu prüfen.
- E5: Reicht ein Journal innerhalb der ~10 Mesh-Primitive, oder bleiben Tools, die die Container indirekt über Snapshots verändern (S5)? Ist kurz prüfbar im Spike.
- E6: Wohin gehört die Morph-/Skin-Datenhaltung (Mesh-Layer vs. Objekt-Struktur)? Core-Frage, laut AD-021 §4.9 erst nach Manus Verdikt.
- E7: Closest-Point-Snapping für Retopo: Weg ist offen.

**Artist-eigen (Manu):**
- A1: Ziel-Größe für *Bearbeitung* (20k? 87,5k?), ATELIER D1c, offen.
- A2: Sind die GPU-Abweichungen akzeptabel (Silhouetten, Pixelzentrum, Sub-Pixel)? Braucht einen Praxis-Check, kann nicht bewiesen werden.
- A3: Reihenfolge AD-022/AD-023 (Manu: "gleich wichtig"; parallel oder nacheinander?).
- A4: Ist der Referenz-PC Untergrenze des Produkts oder nur Testgerät? (REFERENCE_HARDWARE §3). Das entscheidet, ob "GL 3.3 + kein NumPy" bindende Randbedingungen sind.
- A5: Darf die Basis-Topologie gesperrt werden, solange Morph-Ziele existieren? (Workflow-Regel für ARCH-02)
- A6: Sollen Räume als sichtbar getrennte "Rooms" oder als Modi *desselben* Fensters erscheinen (UI-Metapher)? Der Code lässt beides zu.
- A7: Ziel-Reglerverhalten für Morph-Gewicht (J-4, offen): stufenlos oder Schritte?

---

## 10. Empfohlener nächster Schritt

**Kleinste Untersuchung mit dem größten Informationsgewinn: eine Referenz-PC-Messung der Topologie-Op, bevor irgendetwas gebaut wird.** Sie kostet Manu ~10 Minuten und keine Codezeile:

```
python experiments/drag_cost/probe_navigation_gl.py --assets examples/meshes/gollum_20k.obj --scenarios topology --profile-top 0
```

(Befehl aus dem Praktischen Test von drag_cost README, "Slice 2", Schritt 2; `topology` ist dort Teil der Szenarien.) Sie beantwortet E2: ob die Container-Zahl (0,8–1,8 s) auf dem Referenz-PC tatsächlich ~2× liegt und wie sie sich auf History / Sync / Hover-Neupick verteilt. Ergänzend die zwei fehlenden Spike-Schritte (87,5k-Lauf und der Ein-Satz-Flat-Check für E1).

**Danach, falls die Zahlen bestätigen, dass Topologie-Ops dominant bleiben:** der in AD-023 §6 beschriebene Spike in `experiments/` — H0+V0+V2 gemessen plus ein Delta-Prototyp für *zwei* Ops (Delete, Extrude), diesmal mit einem Journal-Prototyp innerhalb der Mesh-Primitive statt Tool-Meldungen. Er entscheidet zwischen B und C mit Zahlen auf dem Referenz-PC: Kommt die Python-Arbeit dort in den Bereich von Zehn-Millisekunden, ist B bestätigt. Bleibt sie bei Hunderten, ist die Frage "andere Auswertung (Arrays/GPU)" berechtigt, aber auch dann nicht automatisch "andere Topologie-Darstellung".

---

### Anhang: Methodik und Grenzen

- Gelesen: AGENTS.md, CLAUDE.md, REFERENCE_HARDWARE, ATELIER, AD-022, AD-023, gpu_picking_spike README, drag_cost README (Referenz-PC-Abschnitte, Audit, Slice 2, Haltepunkt), VIEWPORT_V02_ARCHITECTURE (Ziele, §4.6, §5.4), CORE_V1_FREEZE, V1_CORE (§4, §19), `mesh.py`, `topology.py`, `history.py`, `render_mesh.py`, `derived.py`, `picking_cache.py`, `viewport.py` (Einträge/H7), `application._mesh_transaction`.
- **Nur über Teilbericht eines Hilfs-Agenten**, danach stichprobenhaft geprüft (Scene-Slots, AD-021 §4.9, H7-Regeln): `CORE_API_AUDIT.md`, AD-021 (im Ganzen), Morph-/SubD-Lab-READMEs, ROADMAP-/future_ideas-Abschnitte. Zahlen daraus (Morph-Gewichtsschritt, SubD-Kosten, Objekt-Wechselzeiten) stammen aus diesen Dokumenten.
- **Nicht gelesen:** VIEWPORT_V02_RESEARCH außer Überschriften und §19, AD-018 im Detail, die archivierten Reviews, `SUBDIVISION_SURFACES_RESEARCH.md`, `knife_*`-Implementierungen (nur dass sie die Query-API benutzen).
- **Eigene Messung (Container, nicht Referenz-PC):** `experiments/architecture_audit_probes/probe_mesh_cost.py` (nur lesend, keine Repo-Änderung). Sie bestätigen AD-023 §1 und ergänzen Speicherwerte. Der Snapshot-Speicher ist per tracemalloc gemessen und gilt für CPython 3.13 im Container.
- Die Aussagen zu Blender sind Allgemeinwissen, nicht im Repo oder hier verifiziert.
- Nicht ausgeführt: Tests, Benchmarks gegen die Produktion, GL-Probes (kein Referenz-PC, kein GPU im Container).
