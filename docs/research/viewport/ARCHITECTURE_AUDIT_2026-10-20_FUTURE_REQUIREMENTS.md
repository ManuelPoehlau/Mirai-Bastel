> **Status (2026-10-20):** Detailbericht zu Audit 2 (Zukunftsanforderungen). Discovery, keine Entscheidung. Kurzfassung für Manu: [ARCHITECTURE_AUDIT_2026-10-20.md](ARCHITECTURE_AUDIT_2026-10-20.md).
> Die in §1 ausgewerteten Referenz-PC-Messungen stehen inzwischen in den Mess-Dokumenten (Spike-README „Result: reference PC“, drag_cost-README „Result: topology operations, reference PC“, REFERENCE_HARDWARE §2); die Rohausgaben liegen in `RESULTS_*_2026-10-20.md` neben diesen READMEs. Die Verdikte stehen im Intake Log (2026-10-20): Flat ohne Flecken, keine Dreiecke in Smooth und Flat, flüssig; nur (b) Startlicht ist offen. Der Text unten spricht noch vom Stand „nur Flat“. Zweiter Topologie-Lauf (`--profile-top 15`) und Korrektur zu P0 (c)/N3: [drag_cost-README](../../../experiments/drag_cost/README.md).

# Mirai-Bastel — Future Requirements Architecture Audit

**Modus:** Discovery. Keine Implementierung, keine Repository-Änderung, keine Architekturentscheidung.
**Stand:** `main` @ `435ac7e`, Arbeitsbaum sauber. Dieser Bericht ergänzt [Audit 1](ARCHITECTURE_AUDIT_2026-10-20_VIEWPORT_MESH_WORKSPACES.md) (unverändert gelassen) und überholt dort drei offene Punkte (§1).
**Kennzeichnung:** **[RPC]** Referenz-PC (Q9550, 9800 GTX, GL 3.3.0, Python 3.14.2). **[C]** Container (nicht übertragbar; Python-Code ca. 2× schneller als RPC, GL/Treiber-Anteile nicht). **[H]** Hypothese oder Hochrechnung. **[V]** im Repo/Code verifiziert. **[P]** vorgeschlagen (PROPOSED), nicht entschieden. **[F]** zukünftige Anforderung (Docs/Manu), nicht gebaut.
**Zeitgrenze der Aussagen:** "Zukunftssicher" wird nirgends behauptet. §9 listet, was tatsächlich bewertet wurde und was nicht.

---

## 1. Neue Messungen (Manu, Referenz-PC) und was sie ändern

### 1.1 Topologie-Operationen auf `gollum_20k` [RPC], erstmals auf dem Referenz-PC

n = 3 je Zeile (Median aus 3 Stichproben, **keine p95-Aussage möglich**). ms.

| Operation | Frame gesamt | Op selbst | History | Viewport-Sync | Hover-Neupick | Undo-Frame |
|---|---:|---:|---:|---:|---:|---:|
| Extrude 1 Face | 3 065 | 0,9 | 244 | 2 604 (3 Syncs) | 144 | 1 814 |
| Extrude 20 Faces | 3 599 | 64 | 910 | 2 455 (3 Syncs) | 148 | 1 731 |
| Knife-Commit | 2 360 | 205 | 525 | 1 287 | 245 | 1 992 |
| Dissolve 1 Edge | 1 951 | 32 | 498 | 1 274 | 254 | 1 877 |
| Delete 1 Face | 1 945 | 24 | 465 | 1 265 | 148 | 1 717 |

Vergleich mit den Container-Zahlen aus AD-023 §1 (Frame gesamt 1 273 / 1 834 / 1 188 / 781 / 792 ms): RPC ist **2,0–2,5× langsamer** beim Gesamtframe, beim **Sync 2,7–3,5×**, beim Hover-Neupick ~3×, beim Undo-Frame 1,7–1,9×. Die History ist auf dem RPC **nicht** langsamer als im Container (244–910 vs. 313–889 ms; vermutlich Python 3.14 vs. 3.13, bei n = 3 nicht belastbar). ~~Die Faustregel "RPC ≈ 2× Container" gilt also **nicht** für den GL-/Sync-Anteil.~~ **Korrektur (2026-10-20, später):** Dieser Vergleich kreuzt zwei verschiedene Container (AD-023 vom 2026-10-17 gegen den Container vom 2026-10-20, dessen Sync für denselben Code 1,1–1,6× langsamer ist). Gleicher Tag, gleiche Sonde: RPC/Container ≈ 1,6–2,2× (Frame), 2,0–2,8× (Sync). Die Faustregel gilt grob auch für den Sync.

**Aufschlüsselung am Beispiel Delete (RPC):** Sync 65 % (1 265 von 1 945 ms), History 24 %, Hover-Neupick 8 % (davon 141 ms PickCache-Neuaufbau), Operation 1 %. Ein einzelner Viewport-Strukturneubau kostet auf 21,9k Vertices **~1,26 s**. ~~Extrude zahlt ihn dreimal (begin, erste Bewegung, release).~~ **Korrektur (AD-023-Review B-1, durch den dritten RPC-Lauf bestätigt):** Extrude baut zweimal strukturell neu auf (begin, release) und patcht dazwischen nur Vertices (2 555 ms ≈ 2 × 1 224 ms); die „3 Syncs“ sind drei Frames (`application.py:3039-3108`).

Folgerungen:
1. AD-023 hat den Viewport-Teil (V0/V1/V2) bisher nicht höher bewertet als die History (H0/H1). Auf dem RPC ist **der Viewport-Sync der größte Einzelposten** (55–85 % je Operation), die History der zweitgrößte (8–26 %, bei Dissolve und Extrude 20 Faces ~25 %).
2. Das Picking ist auch hier nur **4–13 %** (Hover-Neupick). AD-022 allein ändert die Topologie-Operation nicht (bestätigt AD-023 §1).
3. Ein Undo kostet ~1,7–2,0 s, fast so viel wie die Operation. "Undo so schnell wie die Operation" (AD-023 Frage 1) ist ohne lokalen Viewport-Patch nicht erreichbar, auch nicht mit Delta-History allein, weil der Neuaufbau des Viewports danach bleibt.
4. ~~Offen bleibt die Aufteilung des Syncs auf dem RPC.~~ **Beantwortet (2026-10-20, dritter Lauf, [Rohausgabe](../../../experiments/architecture_audit_probes/RESULTS_TOPOLOGY_SYNC_SPLIT_REFERENCE_PC_2026-10-20.md)):** ein Strukturneubau 1 224 ms = Normalen/Adjazenz 24 %, Index-Karte mit Triangulierung 42 %, Flatten und Upload 34 % (GL-Store nur ~12 %). Offen: Einfluss des zyklischen GC und der History-Tiefe (AD-023-Review B-1).

### 1.2 GPU-Picking-Spike auf `gollum` 87 500 V [RPC] (neu; vorher nur 20k)

| Zeile (p50, ms) | CPU-Picker | GPU-ID-Buffer |
|---|---:|---:|
| Pick nach Orbit, Vertex / Edge / Face | 662 / 775 / 619 | **14,0 / 15,5 / 11,8** |
| Hover bei gültigem Zustand, Vertex / Edge / Face | 85 / 197 / 35 | **3,3 / 4,1 / 0,65** |
| Box 300 px Vertex | 14 522 | **295** (Tiefen-Variante 332) |
| ID-Render (GL-Timer, GPU-Zeit) | – | 10,3 (Wandzeit 10,8) |
| Aufbau der Spike-eigenen Puffer je Mesh-Zustand (Variante B1, Python) | – | 3 087 |

Übereinstimmung mit dem CPU-Picker (Shaded): Vertex 90,7 % (mit Tiefen-Oracle 96,7 %), Edge 89,0 %, Face 78,7 % + 21,3 % reine Halb-Pixel-Konvention (0 echte Abweichungen). Box 300 px Edge: Variante "ids" verliert 33 % (33 693 statt 49 720), Tiefen-Variante +2,8 % / −0,6 %. Das deckt sich mit den Container-Zahlen (AD-022 §2).

Einordnung: Bei 87,5k liegt ein Pick nach Kamerawechsel mit 14 ms **knapp unter einem 60-Hz-Frame** (16,7 ms), von denen 10,3 ms reine GPU-Zeit des ID-Passes sind. Der Spielraum ist klein; ein Pass, der nur das Ziel der aktuellen Pick-Art zeichnet statt drei Ziele, wäre eine Optimierung **[H]**.

### 1.3 Flat-Shading-Check (Manu: "sieht auch gut aus, keine Flecken")

Das ist Evidenz, dass `gl_PrimitiveID` und die Buffer-Texturen (`texelFetch`, `gl_render_store.py:254`) auf dem RPC-Treiber korrekt arbeiten. Damit ist AD-022 Variante **B2** (ID-Pass aus den `RenderMesh`-Puffern) auf diesem Treiber nicht mehr durch `gl_PrimitiveID` blockiert. **Formal:** `REFERENCE_HARDWARE.md` §2, WP-06 Intake Log (B3c "pending") und ATELIER führen den Punkt noch als offen. Nach AGENTS.md §4a gilt ein Verdikt erst, wenn es im zuständigen Dokument steht. Ich habe nichts geändert; der Eintrag ist Manus Commit bzw. der nächsten Doku-Pflege vorbehalten.

### 1.4 Aktualisierung der offenen Punkte aus Audit 1

| Punkt | vorher | jetzt |
|---|---|---|
| E1 `gl_PrimitiveID` auf RPC | offen | **beantwortet** (visuell, Manu); noch nicht im Repo vermerkt |
| E2 Topologie-Ops auf RPC | nur Container | **gemessen** (§1.1); n = 3, ohne Profil |
| E3 Spike 87,5k auf RPC | fehlte | **gemessen** (§1.2) |
| Entscheidung B1 vs. B2 | an E1 gebunden | spricht für B2; B1 wäre bei 3,1 s Aufbau je Mesh-Zustand ohnehin ausgeschieden |
| Rangfolge AD-023 H vs. V | H1 als Kern gedacht | **V (Viewport) vor H (History)** nach RPC-Anteilen; beide bleiben nötig |

---

## 2. Zukunftsanforderungs-Matrix

**Legende:** ● erforderlich · ○ nützlich · – nicht betroffen. Spalten = Workflows aus dem Auftrag. "Status heute" bezieht sich auf den verifizierten Code.

| # | Fähigkeit | Retopo | Morph (viele Targets) | Interaktive Topo-Tools (Extrude/Bevel) | Attribute & Maps | Workspaces (Rig/Skin/Anim) | Status heute |
|---|---|:-:|:-:|:-:|:-:|:-:|---|
| K1 | Stabile Element-IDs (V/E/F) über Ops und Undo | ● | ● | ● | ● | ● | **vorhanden** [V] (`ids.py`, AD-001) |
| K2 | Face-Corner-Identität (Ecke = Face × Vertex) | – | – | ○ | ● (UV, Split-Normalen, falls geplant) | – | **fehlt**; Boundary wird in-place verändert (`mesh.py:328`) |
| K3 | Mutations-Provenienz (alt → neu, Parameter) | – | ● | ○ | ● | ● | **fehlt** (ARCH-02 offen; CORE_API_AUDIT) |
| K4 | Revision / Änderungsprotokoll im Mesh | ○ | ● | ● | ● | ● | **fehlt**; 24 manuelle Invalidierungsstellen in `application.py` |
| K5 | Attribut-Ebenen je Domäne mit Propagation, Undo, Symmetrie, Serialisierung | ○ | ● | ○ | ● | ● | **fehlt**; nur `symmetry_definition` und Anzeige-Flags |
| K6 | Lokale/Delta-History und Transaktions-Rollback | ● | ○ | ● | ● | ● | **fehlt**; Ganz-Mesh-Snapshots [V], H1 [P] |
| K7 | Lokaler Viewport-Topologie-Sync, stabile Zeilentabelle | ● | ○ | ● | ○ | ○ | **fehlt**; Vollneubau (`render_mesh.py:347`), V1 [P] |
| K8 | Statischer Raumindex (Strahl + nächster Punkt) für große Quellflächen | ● | – | – | ○ | – | **fehlt**; nur Messung im Audit (Scratch), nicht im Repo |
| K9 | GPU-ID-Picking | ● | ○ | ● | ○ | ● | Spike [RPC] belegt, AD-022 [P] |
| K10 | Evaluierte Geometrie (Base → Morph → Skin → SubD) mit definierter Eigentümerschaft | – | ● | ○ | ○ | ● | Prinzip entschieden (AD-021 §4.9), **nicht gebaut** |
| K11 | Pick-Ziel ≠ Anzeige-Ziel, mehrere abgeleitete Flächen | ○ | ● | ○ | ○ | ● | **eingeschränkt**: ein Provider (H7-R4), Picking nur am Käfig |
| K12 | Bulk-Auswertung (NumPy oder GPU) | ○ | ● | ○ | ● | ● | **fehlt**; reines Python, NumPy auf RPC ungeprüft |
| K13 | Parametrische Live-Werkzeuge (Vorschau = Ergebnis aus Ausgangszustand neu ableiten) | ○ | – | ● | – | – | Muster **vorhanden für Extrude** [V]; **Bevel existiert nirgends im Repo** |
| K14 | Undo-Gruppierung je Geste | ● | ● | ● | ● | ● | **vorhanden** (`_mesh_transaction`, `CompositeCommand`) [V] |
| K15 | Workspace-Konfiguration über gemeinsamen Diensten | – | – | – | – | ● | **fehlt**; nur Bausteine |
| K16 | Export/Austausch (Attribute, Targets) | – | ○ | – | ● | ○ | **kein Exporter im Repo** (grep) |
| K17 | Sichtbarkeits-/Masken-Zustand am Mesh (Hide, Isolate, Mask) | ○ | ○ | ○ | ● | ○ | **fehlt**; `Selection` ist Sitzungszustand |
| K18 | Abgeleitete Skalare (Tension, Krümmung) | ○ | ○ | – | ● | ○ | **fehlt** |

Quellen für die Anforderungen: Retopo (RetopoFlow/Quad Draw: Strokes, Contours, Relax, Patches) in `docs/research/MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md:1198,1251,1395`; Morph (mehrere Targets, Topologie-Abhängigkeit) `docs/future_ideas/ANIMATION.md`; Maske/Polygroups/Relax/Hide `docs/future_ideas/MODELING.md`; Auftrag.

**Wichtige Korrekturen an der Dokumentenlage:**
- `docs/future_ideas/MODELING.md` Priorität 2 spricht von einer "bestehenden Bevel-Fähigkeit", die zu auditieren sei. Im gesamten Repo (alle `*.py`, inklusive `experiments/` und `playground/`) gibt es **kein Bevel**. K13 gilt für Bevel daher als *neu zu bauen*.
- Die Future-Ideas für Rigging und Performance sind leere Stubs (`RIGGING.md`, `PERFORMANCE.md`: nur Kopfzeile).

---

## 3. Lückenanalyse gegen die heutige Architektur

Mit "Umkehrkosten" ist gemeint: wie teuer es wird, die Entscheidung *nach* dem Bau erster Features zu ändern (N = niedrig, M = mittel, H = hoch).

| Fähigkeit | Heutige Lage (Beleg) | Lücke | Umkehrkosten | Nötig ab |
|---|---|---|:-:|---|
| K2 Ecken | `_FaceData.boundary` als Liste; `split_edge` fügt in-place ein (`mesh.py:328`); 12 Core-Mutationen ohne Ecken-Provenienz | Ohne Ecken keine UV/Split-Normalen; mit Ecken müssen alle Mutationen sie fortschreiben | **H**, sobald Corner-Daten existieren | erst bei UV/Hard-Edge-Bedarf |
| K3 Provenienz | CORE_API_AUDIT: "no built-in mechanism to identify which operation caused a topology change"; Lab behilft sich mit Heuristik (Mittelpunkt, MEDIUM) | Jede Mutation muss alt→neu melden | **H** (jede später gebaute Mutation und jedes Tool ohne Vertrag erzeugt Nacharbeit) | vor Morph/Skin-Produktion |
| K4 Revision | `picking_cache.py:14-18` nennt es ausdrücklich; V02 §5.4 setzt `topology_revision` voraus | Zähler und Granularität (Position / Topologie / Attribut) | **M** | früh, billig |
| K5 Attribute | Heimat laut AD-021 §4.9 "Mesh oder mit ihm gesnapshottete Struktur" (nicht entschieden); Präzedenz: additiver Schlüssel `"symmetry"` in `export_state` | Speicherform, Domänen, Propagation, Undo | **H** (Dateiformat v3, Undo-Modell, alle Tools) | vor erstem Gewicht/Maske |
| K6 History | `MeshStateCommand` Snapshot (`topology.py:36`); Snapshots auch als Rollback in ≥ 8 Tools | Delta + Rollback-Mechanismus | **M–H** | vor Attributen (Speicher, §4.3) |
| K7 Zeilentabelle / Patch | `_vertex_index`/`_face_row` per Enumeration (`render_mesh.py:176`); GL-Store legt VertexList bei Topologie neu an | stabile ID→Zeile-Tabelle mit Freiliste; Attributkanäle im VertexList | **M** | mit AD-022/023 |
| K8 Raumindex | Audit: BVH 0,65 s / 3,2 s Aufbau [C], Strahl 0,07 ms; kein Code im Repo; "nächster Oberflächenpunkt" hat keinen Pfad | Schnittstelle + Implementierung (statisch) | **N** (reine Zusatzschicht) | erst mit Retopo-Paket |
| K10/K11 Kette | H7: ein Provider, nur Anzeige, Picking am Käfig (AD-013 H7-R1…R4); H7-E ungeprüft | Kette als Stufen mit Dirty-Weitergabe; Pick/Anzeige getrennt | **M–H** | vor Morph+SubD-Kombination |
| K12 Bulk | `import numpy` kommt in `src/` nicht vor; `requirements-dev.txt`: pytest, pyglet | Auswertungsort, Datenlayout | **H** (Layout) / **N** (Backend, wenn Schnittstelle sauber) | vor Morph mit vielen Targets |
| K13 Live-Tools | Extrude: Topologie einmal in `begin()`, danach je Pointer nur `set_vertex_position` (`extrude.py:270-295`), Viewport-Pfad `on_vertices_moved` | Parameter, die die Topologie ändern (Bevel-Segmente), brauchen schnelles Zurücksetzen + lokalen Neuaufbau | **M** | mit erstem Bevel |
| K16 Export | kein Exporter | Format, Attribut-Mapping | **N–M** | spät |

---

## 4. Teure, kaum umkehrbare Entscheidungen

Reihenfolge nach Umkehrkosten × Nähe. Das sind Entscheidungen, keine Empfehlungen.

### 4.1 Wohnort und Schlüssel von Attributdaten
Optionen: (a) Layer im `Mesh`, mit im Snapshot; (b) ID-geschlüsselter Speicher am Objekt, außerhalb des Snapshots; (c) spaltenorientierte Arrays mit ID→Zeile-Abbildung.
- **Verifiziert:** IDs werden nie wiederverwendet (`mesh.py:1111`, AD-001), eine Bindung ist "gültig oder tot, nie falsch" (AD-021 §4.9). Ein Speicher außerhalb des Meshes bleibt unter Undo semantisch sicher, solange Einträge toter IDs nicht wiederverwendet werden. Das ist ein echtes Argument für (b)/(c).
- **Gemessen [C]:** eine skalare Ebene als `dict[int,float]` kostet 2,5 MB bei 21,9k Vertices; als `array('f')` 0,09 MB. Skin-Gewichte mit 4 Einflüssen als Dicts: **9 MB** je Snapshot. Mit dem heutigen Snapshot-Undo (zwei Snapshots je Schritt, zusammen schon ~61 MB bei 21,9k) vervielfacht jede Ebene im Mesh den Undo-Speicher. Die Entscheidung "Attribute im Snapshot" ist daher **nur zusammen mit** einer Delta-History sinnvoll.
- **Spezialfall Morph:** Das Morph Lab speichert Targets als ID-identische Mesh-Kopie (Lab-Konvention, nicht Format; README :175). Für Produktion gilt "nach Manus Verdikt" (AD-021 §4.9). Speicherformat und Auswertungsformat sollten **getrennt** festgelegt werden: Speicherung als dünn besetzte ID-geschlüsselte Deltas (unabhängig vom Backend), die Auswertung baut daraus ihre eigene gepackte Form.

### 4.2 Provenienz-Vertrag der Mutationen (K3)
Ein Journal, das nur "berührte Elemente" meldet, reicht für Delta-Undo und Viewport-Patch; es reicht **nicht** für Attributpropagation, Morph-Remap und Skin-Gewichte, die wissen müssen, *woher* ein neues Element kommt (`split_edge`: Kante → 2 Kanten + Vertex bei Parameter t; `collapse_edge`: Überlebender; `split_face`: 1 → 2; Dissolve: n → 1). Wird das Journal zuerst nur als Touched-Set gebaut und später um Herkunft erweitert, ist jede Mutation und jedes Tool zweimal anzufassen. Ein einziger Vertrag, der beides trägt, ist die billigere Reihenfolge **[H]**. Das ist exakt die Frage ARCH-02 (ROADMAP :390-418).

**Konkrete Lücke im Code, die ein Journal in den `Mesh`-Primitiven nicht sieht:** `Extrude._prune_leftover_geometry` verändert das Mesh über `export_state()` → Dict-Manipulation → `load_state()` (`extrude.py:360-389`), und mehrere Tools nutzen `load_state` als Rollback (Knife, Symmetrischer Knife, Extrude-Cancel, Slide). Ein primitivenbasiertes Journal erfasst diese Änderungen nicht; sie bräuchten entweder einen Diff beim `load_state` oder eine Migration auf Primitive. (Der Core hat seit 2026-10-06 `delete_edges`/`delete_vertices`; ob sie den Extrude-Fall abdecken, habe ich nicht geprüft.)

### 4.3 History-Format
Snapshot (heute) vs. Delta. Die Entscheidung hängt an 4.1 (Speicher) und 4.2 (Journal) und an den ≥ 8 Rollback-Stellen. Gemessen: ein Undo-Schritt auf 21,9k ≈ 61 MB, auf 87,5k ≈ 246 MB **[C]**; `HistoryStack` hat keine Obergrenze. Das ist bereits **heute** ein Speicherrisiko für lange Sitzungen auf 8 GB **[H]**, unabhängig von der Zukunft.

### 4.4 Evaluierte Geometrie und Pick-Ziel
AD-021 §4.9 legt fest: Das Mesh ist die editierbare Rest-Geometrie; die Kette Morph → Skin → SubD erzeugt abgeleitete Positionen, schreibt nie ins Mesh, wird nicht serialisiert und nicht in die History aufgenommen. Offen ist die **Schnittstelle**: Stufen als reine Funktionen mit Dirty-Weitergabe pro Stufe, wo das Ergebnis lebt, und **was gepickt wird**. Befunde:
- Morph Lab: Picking und Auswahl auf der Ruheform, Manu: "hilft" (README 6a). Skinning und Animation brauchen dasselbe, Animation dann auch Picking auf der Pose.
- AD-022 erwähnt weder H7-Flächen noch SubD/Morph (grep). Ein ID-Pass am Käfig mit Tiefe des Käfigs sagt nicht, was am *angezeigten* (geglätteten) Bild sichtbar ist (SubD-Research §6.2: "der Käfig verschwindet in der Fläche"). Das ist eine ungeklärte Wechselwirkung, die vor einer Entscheidung für B2 beachtet werden sollte.
- Positiv: Wenn der ID-Pass dieselben Vertex-Puffer bzw. denselben Vertex-Shader benutzt wie der Beleuchtungs-Pass (B2), erbt er jede GPU-seitige Deformation kostenlos.

### 4.5 Auswertungsort der Deformation (CPU Python / NumPy / GPU)
Gemessen [C], reine Blend-Arithmetik `out = base + Σ wᵢ·Δᵢ` bei 21 875 Vertices, ohne Normalen, Upload, Draw:

| aktive Targets N | Python, dünn besetzt (15 %) | Python, voll besetzt | NumPy, voll besetzt |
|---|---:|---:|---:|
| 1 | 1,5 ms | 7,1 ms | 0,05 ms |
| 10 | 14,0 ms | 61,7 ms | 0,15 ms |
| 50 | 64,9 ms | 372,5 ms | 0,37 ms |

(NumPy-Delta-Speicher bei dichter Ablage: 13 MB bei N = 50.) Auf dem RPC ist für den Python-Anteil grob das Doppelte zu erwarten **[H]**. Zwei Lesarten:
- **Voll neu summieren** ist ab N ≈ 10 bei 20k im Bereich mehrerer Frames; das ist nicht das Muster, das man bauen sollte.
- **Inkrementelle Akkumulation** (bei Slider-Änderung nur `Δw·Δᵢ` im Träger dieses einen Targets addieren) kostet so viel wie die N = 1-Zeile: 1,5 ms (15 % Träger) bzw. 7,1 ms (voll) [C] **[H]** für das Gesamtbild. Sie ist eine Designentscheidung, keine Hardwarefrage, und sie funktioniert auch ohne NumPy. Zu klären: Gleitkommadrift (das Morph Lab zeigt in Review F-8, dass `(1−w)b + wt` unveränderte Bereiche um 1 ulp verschiebt) und Relativ-/Absolut-Semantik.
- Was dann dominiert, sind **Normalen** (Voll-Neuberechnung 112 ms bei 21,9k [C], AD-023) und **Upload**. Der vorhandene Positions-Patchpfad (`render_mesh.py:355`) kostet laut RPC-Messung ca. 0,045 ms je bewegtem Vertex (Body unter Symmetrie, REFERENCE_HARDWARE §2), bei einem Träger von 3 300 Vertices also ~150 ms **[H]**. Mit dem heutigen Pfad scheitert ein Slider auf großen Trägern am Upload je Vertex (`store.update` pro Vertex), nicht an der Blend-Arithmetik. Ein Bereichs-Patch ist Teil des Viewport-Vertrags (AD-018), nicht des Meshs.
- **Skinning** (alle Vertices × Einflüsse je Frame) ist nach demselben Maßstab in reinem Python nicht interaktiv **[H]** und ein klassischer Fall für den Vertex-Shader (Indizes und Gewichte als zwei `vec4`-Attribute; GL 3.3 genügt). Dann braucht die CPU ausgewertete Positionen nur auf Abruf für wenige Vertices.

Die GPU-Variante ist in diesem Repo **nicht gemessen**. Offen sind u. a. `GL_MAX_VERTEX_ATTRIBS`, `GL_MAX_TEXTURE_BUFFER_SIZE` und die Grafikspeicher-Obergrenze (Windows zeigt 481 MB) auf dem RPC (P0).

### 4.6 Spaltenlayout der Positionen
`mesh.py:14-17` schreibt den Positionszugriff ausschließlich über `vertex_position()`/`set_vertex_position()` vor. Ein Austausch der **Position-Speicherung** (Dict von Dataclasses → Arrays mit ID→Zeile) ist daher API-kompatibel und lokal in einer Datei möglich. Das ist eine verifizierte Eigenschaft, die einen Teil der "großen Redesign"-Kosten vermeidet. Sie hilft nur, wenn eine Bulk-Auswertung (K12) tatsächlich verfügbar ist; sonst bringt ein Array-Layout in reinem Python nichts.

### 4.7 Weitere, weniger dringende
- **Zeilentabelle der Puffer** (K7): ohne stabile ID→Zeile-Abbildung baut weder inkrementelles Patchen noch der ID-Pass (B2). Sie muss *einmal* festgelegt werden und gilt für Geometrie, ID-Pass und Attributkanäle.
- **Raumabfrage-Schnittstelle** (K8): billig umkehrbar, solange nur die Schnittstelle (`ray`, `closest_point`, `statisch`) festliegt.
- **Objekt-Schlüssel** `(ObjectId, ElementId)` (AD-021): bereits entschieden und verifiziert, gut.

---

## 5. Morph, Skinning und SubD gemeinsam; arbeitsraumspezifische Flächen

**Reihenfolge der Kette:** Basis → Morph → Skin → SubD. SubD zuletzt (Mesh-Docstring `mesh.py:14-17`; SubD-Research §7.4; AD-021 §4.9).

**Lastprofil:** Beim Modellieren sind SubD-Änderungen lokal (ein Kontrollvertex beeinflusst auf Stufe 2 nur 1–4 % der abgeleiteten Vertices, SubD-Research §5.2). Bei jedem Slider- oder Pose-Frame ist es dagegen "alle Positionen geändert". Das spricht für Stencils (Topologie einmal, Positionen oft). Gemessen im Subdivision Lab [C]: Drag-Schritt Head Stufe 2 148 ms, Stufe 3 2 845 ms; **1,64 von 1,80 s liegen in `GLRenderStore._patch_attribute`**, das den gesamten CPU-Puffer schreibt, nicht in der Stencil-Rechnung (~3 ms). Das ist ein bereits sichtbarer, billiger Hebel im Viewport-Vertrag, unabhängig von der Mesh-Frage.

**Gleichzeitigkeit heute:** Morph und SubD lassen sich im Lab nicht zusammen anzeigen (H7: ein Provider, Morph Lab README :155). H7-E (Ersatzflächen für Objekt-Einträge) ist laut AD-013 nicht unabhängig reviewt.

**Skizze (kein Vorschlag zur Umsetzung):** Jeder sichtbare Eintrag hat eine Liste von Auswertungsstufen. Jede Stufe liefert Positionen für die nächste, mit eigenem Dirty-Zustand. Jeder Eintrag hat ein *Pick-Ziel* (Käfig / Ruheform / ausgewertete Form) getrennt vom *Anzeige-Ziel*.

| Raum | Pick-Ziel | Anzeige-Ziel | Besonderheit |
|---|---|---|---|
| Model | Käfig | Käfig + SubD-Fläche | SubD nur Anzeige (H7-R2) |
| Morph | Ruheform der Basis (Manu: "hilft") | Mischung; Ziel als eigenes Objekt | Gewichte nicht gespeichert (Manu) |
| Retopo | neues Mesh; Quelle nur als Trefferfläche | beide | Quelle statisch, evtl. 87,5k+ |
| Skinning | Ruheform | Pose + Gewichtsfarben | Gewichtskanal im VertexList (fehlt) |
| Animation | ausgewertete Pose | ausgewertete Pose | später |

---

## 6. Referenz-Hardware: Anforderung oder Optimierung?

**Architektur-Anforderungen (müssen von Anfang an gelten, sonst teure Umbauten):**
- Alle Datenwege inkrementell oder bereichsweise. O(Mesh)-Arbeit pro Pointer-Update oder pro kleiner Operation ist auf dem RPC bei 20k bereits 1–2 s, bei 87,5k 4× mehr (§1.1).
- Auswertungs- und Speicherformat getrennt (§4.1), damit das Backend gewechselt werden kann.
- GL-3.3-konform: Compute/Tessellation entfallen. FBO, `glReadPixels`, Timer-Query, `gl_PrimitiveID`, Buffer-Texturen sind auf dem RPC belegt.
- Keine harte NumPy-Abhängigkeit, solange sie auf dem RPC nicht nachgewiesen ist (REFERENCE_HARDWARE §2: Q9550 ohne SSE4.2/AVX; "bei Upgrades zu prüfen").
- Speicher: Undo-Schritte dürfen nicht proportional zur Mesh-Größe wachsen (§4.3). 481 MB Grafikspeicher begrenzen Delta-Texturen: N × V × 12 B = 13 MB bei N = 50, V = 21,9k; ~105 MB bei N = 100, V = 87,5k **[H, Rechnung]**.

**Optimierungen, die später kommen können, wenn die Schnittstellen stehen:** konkreter Raumindex (BVH vs. Gitter), GPU- vs. CPU-Picking-Variante, Pass-Reduktion im ID-Render, LOD, Bereichs-Upload-Feinheiten, NumPy, Mehrprozess-Parallelisierung (REFERENCE_HARDWARE §4 verlangt, sie als Konflikt zu melden).

**Nicht auf Hardware-Upgrade wetten:** Die geplante Aufrüstung macht den Faktor kleiner, aber nicht O(Mesh) pro Aktion. Der RPC bleibt als Worst-Case-Baseline erhalten (REFERENCE_HARDWARE §5). Ob er die Produkt-Untergrenze ist, bleibt Artist-Entscheidung.

---

## 7. Optionen A / B / C gegen aktuelle Engpässe und Zukunftsworkflows

Alle Aussagen "erfüllt/erfüllt nicht" sind **Bewertung auf Basis der Evidenz in diesem Bericht**, nicht Garantien.

| Kriterium | **A — Inkrementell** (AD-022 B2 + H0 + V0 + V2, kein Core-Eingriff) | **B — Selektiv umbauen** (A + Mesh-Journal mit Provenienz, Revision, O(1)-Adjazenz, Delta-History, Zeilentabelle + Bereichs-Patch, Pick-Dienst, Provider-Liste / Kette, Attribut-Layer-Vertrag) | **C — Großer Neuentwurf** |
|---|---|---|---|
| Pick-Latenz (20k/87,5k, RPC) | gelöst (3,3 / 14 ms) | gleich | gleich |
| Topologie-Op und Undo (20k, RPC ~2 s / ~1,8 s) | H0/V0 grob ~2× [H]; bleibt im Sekundenbereich | Ziel: Zehn-Millisekunden-Bereich [H]; **unbewiesen auf RPC**, Prototyp P2 | nicht belegt |
| Retopo (Quelle statisch, Snapping) | CPU-Cache: 2/8 ms bei gültigem Cache, +107/526 ms [C] nach Kamerawechsel | + K8 Index/GPU-Tiefe als Zusatz | ähnlich |
| Viele Morph-Targets | scheitert an Auswertung/Upload ab N ≈ 10 bei 20k (§4.5) | inkrementelle Akkumulation + Bereichs-Patch möglich; Bulk/GPU offen | Bulk eingebaut, aber Backend ungeprüft |
| Attribute (Gewichte, Maske, UV) | nicht vorbereitet; Speicherproblem im Snapshot (9 MB/Layer) | Vertrag vorhanden (K3, K5, K6) | eingebaut, falls SoA |
| Live-Tools (Bevel mit Segmenten) | Segmentwechsel = Vollneubau (~1,3 s je Sync [RPC]) | schnelles Zurücksetzen + lokaler Neuaufbau (P6) | möglich |
| Workspaces / Raumwechsel | Wechsel O(Mesh) (2,6–3,0 s [C]) | Eintragscache + Konfigurationsrahmen | beliebig |
| Regressionsrisiko | gering | mittel (Core-interne Ausnahme; Debug-Modus "Delta == Snapshot") | **hoch**: ~3 200 Testfunktionen (2 161 in `tests/`) als Netz, alle Tool-Verträge neu zu bestätigen |
| Pflegelast | klein | mittel | groß, Doppelpflege während Migration |
| Bewiesen durch | AD-022-Spike [RPC], Slice-1/2-Äquivalenztests | **nichts davon auf RPC**; AD-023 §6 verlangt erst den Spike | nichts |

**Was C wirklich wäre.** Die Zukunftsanforderungen zeigen, dass *Half-Edge/BMesh nicht* der naheliegende Kandidat für "C" ist. Die Anforderungen K5, K6, K12 (Attribute, Snapshot-Kosten, Bulk-Auswertung) zielen auf ein **spaltenorientiertes (Structure-of-Arrays) Layout mit ID→Zeile-Abbildung**, nicht auf eine andere Topologie-Navigation. Der Teil davon, der die Positionen betrifft, ist wegen `vertex_position()`-Vertrag (§4.6) *lokal*. Der Teil, der die Topologie betrifft (12 Primitive, ~35 Schreibstellen in `mesh.py`, alle Tools darüber), ist der teure. Deshalb ist die plausible Zwischenstufe: **Topologie bleibt dictbasiert mit dichter Query-API; Positionen und Attribute werden spaltenorientiert**. Das wäre Option B plus Layout-Wechsel, noch kein Neuentwurf. Half-Edge bleibt gerechtfertigt, wenn eine konkrete Ecken-/Radial-Operation (z. B. Retopo-Strip-Tools, SubD-Pole) nicht aus `vertex_edges` + Geometrie lösbar ist.

**Bewertung:** Auf Basis der Evidenz ist B die einzige Option, die alle fünf Workflow-Spalten adressiert, ohne dass etwas davon auf dem RPC belegt wäre. A allein reicht nicht für Morph/Attribute/Live-Tools. C ist durch keine Messung gestützt. Das ist eine Hypothese; sie wird durch die Prototypen in §8 geprüft, nicht entschieden.

---

## 8. Fundamente früh festlegen, und was warten kann

**Früh klären (teuer zu ändern; zunächst als Entscheidung/Schnittstelle, nicht als Implementierung):**
1. Journal- und Provenienz-Vertrag der Mutationen (K3, K4) inklusive Umgang mit `load_state`-Mutationen.
2. Wohnort und Schlüssel von Attributdaten; Speicher- vs. Auswertungsformat (K5, §4.1).
3. History-Modell Snapshot vs. Delta, inkl. Rollback-Stellen (K6).
4. Zeilentabelle + Bereichs-Patch im Viewport-Vertrag (K7); damit auch der ID-Pass von AD-022 (B2).
5. Auswertungsstufen-Schnittstelle und Pick-Ziel ≠ Anzeige-Ziel (K10, K11), inkl. Wechselwirkung mit AD-022.
6. Auswertungsort-Frage (CPU inkrementell / NumPy / GPU), mindestens die Messlage dafür (K12).

**Kann warten (Schnittstelle genügt, Implementierung später):** konkreter Raumindex (K8), Bevel (K13 als Muster vorhanden), Export (K16), abgeleitete Skalare (K18), Rig-/Skin-Daten, Animation, Corner-Domäne (K2), solange keine UV/Split-Normalen geplant sind, Masken-UI (K17, aber sein Datenvertrag gehört zu 2.).

**Bereits billig und unabhängig, kein Architekturentscheid nötig (nur zur Einordnung):** Bereichs-Upload statt Voll-Puffer in `_patch_attribute`; Extrude-Syncs auf einen reduzieren (V2); H0.

---

## 9. Prototypen- und Messplan mit Erfolgskriterien

Alle Kriterien sind **Vorschläge** (PROVISIONAL). Das Ziel "Blender-Niveau" ist von Manu bisher qualitativ formuliert; ich nehme als Arbeitsmaß *16,7 ms pro Pointer-Update (p95)* und *≤ 100 ms für diskrete Aktionen* an. Das ist **Artist-Entscheidung** (§10) und wird vor dem Bau bestätigt. Alles in `experiments/`, kein `src/`-Eingriff.

| # | Frage | Experiment (klein) | Erfolgskriterium | Warum jetzt |
|---|---|---|---|---|
| **P0** | Welche Randbedingungen hat der RPC wirklich? | Manu, ohne Code im Repo: (a) `pip install numpy` in einem venv, danach `import numpy` und das Blend-Skript (Anhang A); (b) GL-Limits ausgeben (Anhang B); (c) `probe_topology_sync_split.py` (**Korrektur 2026-10-20:** ursprünglich stand hier `probe_navigation_gl.py --scenarios topology --profile-top 15`; `--profile-top` profiliert aber nur orbit/zoom/first_hover, nicht topology); (d) Flat-Verdikt im Repo vermerken | NumPy läuft (ja/nein) mit Zahlen; GL-Limits vorhanden; Sync-Anteile Triangulierung / Normalen / Puffer auf RPC | beantwortet K12 und V-Gewichtung ohne Bau |
| **P1** | Lässt sich ein Journal in den Mesh-Primitiven vollständig machen? | Subklasse oder Wrapper des Mesh im Experiment; Journal protokolliert Touched-Sets **und** Herkunft für Delete, Dissolve, Extrude, Split, Knife-Commit | (i) Wiedergabe des Journals auf dem Vorzustand ergibt `export_state` **bitgleich** (IDs, Zähler) für alle fünf Ops auf head/body/gollum_20k; (ii) Liste aller Mutationen außerhalb der Primitive (erwartet: Extrude-Prune, Rollback-`load_state`) ist vollständig; (iii) Journal-Mehraufwand ≤ 5 % der Op-Zeit | entscheidet 4.2 und die Machbarkeit von B |
| **P2** | Erreicht lokaler Delta-Undo + Viewport-Patch den ms-Bereich auf dem RPC? | AD-023 §6: Delete und Extrude auf gollum_20k, Delta-Entry + Patch der Triangulierung/Normalen/Puffer | Op + History + Sync ≤ 100 ms p50 und Undo ≤ 100 ms auf RPC (Basis: 1 945 / 3 065 ms bzw. 1 717 / 1 814 ms); Puffer == Vollneubau; Speicher je Undo-Schritt ≤ 1 % des Snapshots (~61 MB); n ≥ 15, p95 angeben | **die** Entscheidung B vs. C |
| **P3** | Trägt der Attribut-Vertrag? | Spaltenorientierte Ebenen: Maske (Skalar), Gewichte (4 Einflüsse); Propagation über Split/Collapse/Dissolve per Provenienz aus P1; Undo per Delta; Symmetriespiegelung; Serialisierung; Anzeige als Vertexkanal | Rundreise bitgleich; Propagationsinvarianten (Gewichtssumme = 1, Maske stetig); Undo stellt Zustand her; Speicher je Snapshot-Äquivalent ≤ Array-Größe (0,09 MB/Skalar-Ebene bei 21,9k); Overlay-Update ≤ 16,7 ms p95 RPC | prüft K2/K3/K5/K6 zusammen |
| **P4** | Tragen viele Morph-Targets? | N = 1, 10, 50 aktiv, 15 % und 100 % Träger, 20k und 87,5k; Backends: (i) Python inkrementell, (ii) NumPy (falls P0 ja), (iii) GPU-Vertex-Shader mit Buffer-Textur; gemessen wird die *gesamte* Slider-Kette (Blend + Normalen + Upload + Draw) | ≤ 16,7 ms p95 auf RPC bei 20k, N = 10, 15 % Träger; Drift der Akkumulation nach 10 000 Bewegungen ≤ 1e-6 relativ oder periodisches Neu-Summieren mit Kosten ≤ 50 ms; Grenze (N, V) je Backend dokumentiert | entscheidet 4.5 / K12 |
| **P5** | Reicht ein statischer Index für Retopo-Snapping? | BVH oder Gitter über die statische Quelle (21,9k, 87,5k): Strahl, nächster Punkt; Alternative: GPU-Tiefe pro Kamerazustand | Aufbau ≤ 3 s (87,5k) einmalig; Strahl ≤ 0,2 ms, nächster Punkt ≤ 1 ms; Stroke mit 200 Samples + 20 projizierte Vertices je Bewegung ≤ 8 ms p95 RPC; GPU-Tiefenvariante: ≤ 14 ms je Kamerazustand (+ Auslesung) | liefert K8 und die AD-022-Option-A-Frage |
| **P6** | Tragen Live-Tools mit Topologie-Parametern (Bevel-Muster)? | Platzhalter-Tool (Kanten-Chamfer mit Segmentzahl) auf Delta-Restore aus P2 | Segmentwechsel ≤ 33 ms p95 bei 20k; Abbruch stellt `export_state` bitgleich her; ein History-Eintrag je Geste | prüft K13 ohne Bevel zu bauen |
| **P7** | Morph + SubD gleichzeitig, Pick am Käfig | Provider-Liste im Experiment (H7-Erweiterung nur dort), Head Stufe 1–2 | beide sichtbar, Käfig-IDs und Picks unverändert, Slider-Schritt ≤ 16,7 ms p95 auf Head; Verhalten des ID-Passes bei Käfig-vs-Fläche-Sichtbarkeit dokumentiert | klärt §4.4 und die AD-022-Lücke |
| **P8** | Funktioniert B2 mit stabiler Zeilentabelle? | ID-Pass aus den `RenderMesh`-Puffern mit `gl_PrimitiveID`, Zeilentabelle mit Freiliste | Übereinstimmung ≥ Spike-Werten (§1.2); kein zusätzlicher Aufbau; W-Drag-Mehrkosten ≤ 0,5 ms; Ergebnis nach einem Delta-Patch (P2) korrekt | verbindet AD-022 und AD-023 |
| **P9** | Wie teuer ist der Raumwechsel? | Eintragscache für Edit-Objekt-Wechsel über vorhandene `set_object_entry`/`set_edit_mesh` | Wechsel ≤ 100 ms bei 20k (Basis 2,6–3,0 s [C]) | K15 |

**Reihenfolge:** P0 → (P1 ∥ P5) → P2 → P3/P4/P8 → P6/P7/P9. Entscheidungspunkte: nach **P2** (B vs. C), nach **P4** (Auswertungsort), nach **P1+P3** (Attribut-/Provenienz-Vertrag).
**Nicht prototypen:** Half-Edge-Kern, Rig/Skin/Animation-Datenmodelle, GPU-Compute.

---

## 10. Offene Fragen

### Engineering (nicht aus dem Repo beantwortbar)
- **N1** NumPy auf dem Q9550: lauffähig (Wheel für Python 3.14)? (P0)
- **N2** GL-Limits des RPC-Treibers: `GL_MAX_VERTEX_ATTRIBS`, `GL_MAX_TEXTURE_BUFFER_SIZE`, tatsächlicher VRAM. (P0)
- **N3** Aufteilung des Syncs (Triangulierung / Normalen / Upload) auf dem RPC. (P0)
- **N4** Reicht ein primitivenbasiertes Journal, oder sind `load_state`-Mutationen (Extrude-Prune, Rollbacks) ein strukturelles Problem? (P1)
- **N5** Zeilentabelle: Freiliste mit Lücken vs. Kompaktion; Auswirkung auf den ID-Pass. (P8)
- **N6** Wechselwirkung ID-Pass ↔ SubD/Morph-Anzeige (Käfig-Tiefe vs. Fläche). (P7)
- **N7** Closest-Point-Snapping für Retopo: Weg und Kosten. (P5)
- **N8** Gleitkommadrift und Normalenstrategie bei inkrementeller Morph-Akkumulation. (P4)
- **N9** Berührt eine Delta-History die Symmetrie-Verträge AD-SYM-02/03 (eine Geste = ein Eintrag)? Zu prüfen im Rahmen von P2 mit symmetrischem Extrude.
- **N10** Ist Python 3.14 (RPC) vs. 3.13 (Container) bei der History der Grund für die abweichende Skalierung? Bei n = 3 nicht entscheidbar.

### Artist-eigene Workflow-Entscheidungen (Manu)
- **A1** Zielwerte: ab wann ist es "Blender-flüssig" (Pointer-Update, diskrete Aktion, Undo) und bei welcher **Bearbeitungsgröße** (20k oder 87,5k, Retopo-Quelle)? Basis aller Erfolgskriterien in §9.
- **A2** Gewicht-Slider: stufenlos (J-4, offen) und wie viele Targets gleichzeitig sind realistisch (10? 50? 100?). Entscheidet, ob N ≈ 10 oder N ≈ 50 die Planungsgröße ist.
- **A3** Darf die Basis-Topologie gesperrt werden, solange Morph-Targets existieren, oder sollen Topologieänderungen Targets automatisch übertragen (ARCH-02)?
- **A4** Werden UVs, Split-Normalen oder Hard-Edges geplant? Davon hängt ab, ob die Ecken-Domäne (K2) überhaupt gebraucht wird.
- **A5** Sollen Maske, Hide/Isolate, Polygroups **in der Datei** leben (Teil des Meshes) oder Sitzungszustand bleiben (Selektion)? (ANIMATION.md koppelt sie an Morph-Shaping.)
- **A6** Gewichte (Morph-Gewicht, Skin) sind laut Manu für Morph "keine Dokumentdaten". Gilt das auch für Skin-Gewichte (diese sind zwangsläufig Dokumentdaten)?
- **A7** Retopo: Reicht "Treffer entlang des Sichtstrahls" oder ist "nächster Oberflächenpunkt" (Relax, Projektion) Pflicht? Bestimmt GPU-Tiefe vs. Raumindex.
- **A8** Räume als sichtbar getrennte Arbeitsräume oder Modi desselben Fensters; Raumwechsel erlaubt Wartezeit (heute 2,6–3,0 s [C])?
- **A9** Referenz-PC: Untergrenze des Produkts oder Testgerät (REFERENCE_HARDWARE §3)? Bestimmt, ob "kein NumPy, GL 3.3" bindend bleibt.
- **A10** Bevel: Welche Varianten (Edge/Vertex, Segmente, Profil)? Dokumentenlage widersprüchlich (§2).

---

## 11. Was tatsächlich bewertet wurde, und was nicht

**Bewertet (Quelle in Klammern):**
- Topologie-Ops auf RPC (5 Fälle, n = 3), GPU-Picking auf RPC (20k, 87,5k, Head, Body), Flat-Shading (visuelle Aussage), Container-Messungen von Mesh-Abfragen, Snapshot-Speicher, Blend-Arithmetik, Attributspeicher.
- Code: `mesh.py`, `topology.py`, `history.py`, `render_mesh.py`, `derived.py`, `picking_cache.py`, `viewport.py` (Einträge/H7), `extrude.py`, `application._mesh_transaction/_extrude_*`, `scene.py`. Dokumente: AD-021 §4.9, ROADMAP ARCH-02/Deformation, future_ideas, SubD-Research §4–7, Morph-/SubD-Lab (über Hilfs-Agent und Stichprobe), CORE_API_AUDIT (über Hilfs-Agent).
- Zählung der Tests (2 161 Testfunktionen in `tests/`, 711 in `playground/tests`, 274 Symmetry Lab, 78 SubD Lab, 38 Morph Lab): nur gezählt, **nicht ausgeführt**.

**Nicht bewertet:**
- GPU-seitige Morph-/Skin-Auswertung und NumPy auf dem RPC (nur Container).
- Closest-Point-Abfrage, Strokes, Relax/Patches (Retopo-Werkzeuge existieren nicht im Repo).
- Bevel, UV, Export (existieren nicht im Repo).
- Rig/Skin-Datenmodelle (nur Reserve-Slots in `Scene`).
- p95-Werte der Topologie-Ops (n = 3), Streuung, Speicherdruck langer Sitzungen auf dem RPC.
- Ob ein Journal in den Primitiven tatsächlich lückenlos ist (P1).
- Alle Aussagen zu Blender/TopoGun/RetopoFlow sind Literatur- bzw. Allgemeinwissen aus den Repo-Research-Dokumenten, nicht von mir geprüft.

---

## Anhang A — Blend-Messung (Container, zur Wiederholung auf dem RPC)

Datei: `experiments/architecture_audit_probes/probe_morph_blend.py` (nur lesend, reines Python + optional NumPy). Aufruf: `python experiments/architecture_audit_probes/probe_morph_blend.py 21875`. Sie misst nur die Blend-Arithmetik und die Attribut-Speichergrößen, keine Normalen und keinen Upload.

## Anhang B — GL-Limits (ungetestet; kein pyglet/GPU im Container)

```python
import pyglet
from pyglet import gl
w = pyglet.window.Window(visible=False)
def i(n):
    v = gl.GLint(); gl.glGetIntegerv(n, v); return v.value
print("MAX_VERTEX_ATTRIBS", i(gl.GL_MAX_VERTEX_ATTRIBS))
print("MAX_TEXTURE_BUFFER_SIZE", i(0x8C2B))
print("MAX_TEXTURE_SIZE", i(gl.GL_MAX_TEXTURE_SIZE))
print("MAX_VERTEX_UNIFORM_COMPONENTS", i(0x8B4A))
```

Hinweis: Das Snippet habe ich nicht ausgeführt. Die Konstanten `0x8C2B` (`GL_MAX_TEXTURE_BUFFER_SIZE`) und `0x8B4A` (`GL_MAX_VERTEX_UNIFORM_COMPONENTS`) stammen aus meiner Erinnerung der GL-Spezifikation und sollten vor Gebrauch gegen `pyglet.gl` geprüft werden.
