# Architektur-Audit Viewport, Mesh & Workspaces — Kurzfassung für Manu

**Status:** Discovery-Ergebnis eines Agenten (2026-10-20, `main` @ `435ac7e`). Keine Entscheidung, nicht Artist-validiert.
**Ausführlich:** [Audit 1: Viewport, Mesh, Workspaces](ARCHITECTURE_AUDIT_2026-10-20_VIEWPORT_MESH_WORKSPACES.md) und [Audit 2: Zukunftsanforderungen](ARCHITECTURE_AUDIT_2026-10-20_FUTURE_REQUIREMENTS.md) (inkl. Anforderungsmatrix und Prototypen-Plan P0–P9). Die Container-Messungen daraus: [`experiments/architecture_audit_probes/`](../../../experiments/architecture_audit_probes/README.md).
**Zahlen:** **[RPC]** = Referenz-PC (Manu, 2026-10-20; eingetragen in [`REFERENCE_HARDWARE.md`](../../architecture/REFERENCE_HARDWARE.md) §2, [Spike-README](../../../experiments/gpu_picking_spike/README.md) und [drag_cost-README](../../../experiments/drag_cost/README.md)). **[C]** = Container, nicht übertragbar. **[H]** = Hypothese.

## Ergebnis

Ein großer Neuentwurf ist durch die Evidenz **nicht** gerechtfertigt. Die stärkere Hypothese ist ein **selektiver Umbau**: erst die Schritte ohne Core-Änderung, dann gezielte Core-interne Ergänzungen, **wenn** ein Prototyp sie auf dem Referenz-PC bestätigt. Das ist eine Hypothese, kein Beweis.

## Was auf deinem PC gemessen ist (gollum_20k, 21 875 V; p50)

| | CPU heute | GPU-ID-Picking (Spike) |
|---|---:|---:|
| Pick nach Orbit (Vertex) | 161 ms | 3,3 ms |
| Hover, gültiger Zustand (Vertex) | 18,6 ms | 1,65 ms |
| Box 300 px (Vertex) | 2 384 ms | 89 ms |

Bei 87 500 V: Pick nach Orbit 662 → 14 ms, Box 14,5 s → 295 ms; ID-Render 10,3 ms GPU-Zeit (knapp unter einem Frame). Die GPU-Treffer decken sich mit dem CPU-Picker wie im Container (Vertex 91 %, mit Tiefen-Oracle 97 %; Box-Variante „ids“ verliert 33 % der Kanten, die Tiefen-Variante nicht). Flat Shading ohne Flecken, keine Dreiecke in Smooth und Flat und flüssiges Arbeiten (deine Sätze, eingetragen im Intake Log 2026-10-20) sprechen dafür, dass `gl_PrimitiveID` auf deinem Treiber geht.

**Topologie-Operation auf gollum_20k (RPC, je nur 3 Stichproben):** Delete 1,9 s, Dissolve 2,0 s, Knife 2,4 s, Extrude 3,1–3,6 s; Undo 1,7–2,0 s. Davon sind **55–85 % Viewport-Neuaufbau** (ein Neuaufbau ≈ 1,26 s), 8–26 % History-Snapshots, nur 4–13 % Picking. GPU-Picking (AD-022) macht Topologie-Operationen **nicht** schneller.

## Wichtigste Befunde

0. **AD-022 und AD-023 sind nach den Reviews überarbeitet (2026-10-20); jede Review-Anmerkung hat im AD eine Disposition (Abschnitt „Review disposition“). Nicht entschieden.**
0. **Stand 2026-10-20 später:** Beide ADs sind unabhängig reviewt (ACCEPT WITH CHANGES, [AD-022](../../archive/viewport_v02/reviews/AD-022_REVIEW_CLAUDE_001.md), [AD-023](../../archive/viewport_v02/reviews/AD-023_REVIEW_CLAUDE_001.md)). Dein Zerlegungslauf auf dem Referenz-PC: ein Viewport-Neuaufbau (1 224 ms) besteht zu ~88 % aus Python-Arbeit am ganzen Mesh (Normalen 24 %, Triangulierung ~37 %, Flatten ~22 %), nur ~12 % GL. Extrude baut zweimal neu auf, nicht dreimal (Korrektur). Die AD-023-Review nennt den zyklischen Garbage Collector als wahrscheinlich größten Posten der Snapshot-Zeit im Container. Auf deinem PC (gemessen, n = 12, Tiefe 20) ist der Median davon **unabhängig**; der GC verursacht nur einzelne Hänger (bis 12,9 s), `gc.freeze()` macht es langsamer. Bei Delete sind 75 % der Zeit Viewport-Neuaufbau, eine perfekte Delta-History spart höchstens ~12 %.
1. **Der Draw ist nicht der Engpass**, Picking nach Kamerawechsel ist mit GPU-Picking auf deinem PC gelöst (im Spike). Offen ist die Topologie-Operation samt Undo (AD-023): erst der Viewport-Teil, dann die History.
2. **Half-Edge/BMesh löst das nicht.** Es löst nur eine konkrete Schwäche: keine geordnete Ecken-Navigation. Die Ganz-Mesh-Arbeit in reinem Python bleibt.
3. **Konkrete Mesh-Schwächen:** keine Revision und kein Änderungsprotokoll (24 manuelle Invalidierungsstellen in `application.py`); `vertex_edges` ist O(E); die History hat keine Obergrenze (ein Undo-Schritt ≈ 61 MB bei 21,9k, ≈ 246 MB bei 87,5k **[C]**); Snapshots dienen auch als Rollback in ≥ 8 Tools; Extrude verändert das Mesh an den Primitiven vorbei (`load_state`).
4. **Teuer umzukehren, deshalb früh klären:** Wohnort der Attribute (Gewichte, Masken; im Snapshot vervielfachen sie den Undo-Speicher), Herkunfts-Vertrag der Mutationen (ARCH-02), History-Format, stabile Zeilentabelle im Viewport, Schnittstelle für ausgewertete Geometrie (Basis → Morph → Skin → SubD) mit Pick-Ziel ≠ Anzeige-Ziel.
5. **Viele Morph-Targets:** Vollständig neu summieren ist ab ca. 10 Targets bei 20k zu langsam (62 ms in Python, 0,15 ms mit NumPy **[C]**); inkrementelle Akkumulation (nur das bewegte Target) kostet wie 1 Target. Aktuelles NumPy ist auf deinem PC nicht lauffähig, ein älteres unter Python 3.12 importiert. Für viele Targets bleiben also die inkrementelle Rechnung in Python, ein gepinntes NumPy (müsste ausdrücklich entschieden werden) oder die Auswertung auf der Grafikkarte. Danach zählen Normalen und der Upload je Vertex.
6. **Workspaces** sind als Konfiguration über gemeinsamen Diensten plausibel, nicht als eigene Renderer. Heute kostet der Wechsel des Edit-Objekts 2,6–3,0 s **[C]**; Morph und SubD lassen sich nicht zusammen zeigen (ein Provider).
7. **Dokumentenlage:** Im ganzen Repo gibt es **kein Bevel** (`future_ideas/MODELING.md` spricht von einer „bestehenden Bevel-Fähigkeit“), und keinen Exporter.

## Wartet auf dich

1. **Messen:** Zerlegung und GC-Läufe sind erledigt (Drilldown in der drag_cost-README). NumPy ist beantwortet: **das aktuelle NumPy (2.5.4, Python 3.14) startet auf deinem PC nicht** (verlangt x86-64-v2; dein Core 2 hat kein SSE4.2), **NumPy 2.2.6 unter Python 3.12.10 (dein PyCharm-Interpreter) importiert dagegen** (Rechenzeit nicht gemessen). Alle Zeitmessungen liefen bisher unter 3.14.2; ein Lauf unter 3.12.10 steht aus. (a) NumPy in einer eigenen venv auf deinem PC testen: `python -m venv .venv_np`, `.venv_np\Scripts\pip install numpy`, `.venv_np\Scripts\python -c "import numpy; print(numpy.__version__)"`; bei Fehlern die Meldung kopieren. (b) erledigt (Zerlegung, siehe 0.). Offen ist die GC-Messung der AD-023-Review: dreimal `python experiments/architecture_audit_probes/probe_topology_sync_split.py --steps 12 --row-seconds 120 --history-depth 20 --gc on` (dann `--gc off`, dann `--gc freeze`), jeweils die ganze Ausgabe kopieren (je ca. 5 Minuten; Tiefe 20 belegt grob 1,2 GB RAM).
2. **Restliche Verdikte (ATELIER B3):** Flat, „keine Dreiecke sichtbar“ und „läuft flüssig“ sind eingetragen (Intake Log 2026-10-20). Offen bleibt nur (b): Startlicht „Raitt 2:1“ und Kamera ↔ Welt.
3. **Vier Antworten (Stand 2026-10-20: beantwortet sind „flüssig“ = ohne sichtbare Verzögerung, 32 Undo-Schritte, wichtig Knife/Extrude/Connect/Soft Selection „alle“, Morph-Targets 20–50 ohne Limit; offen: Sperre der Basis-Topologie, UVs/Hard-Edges):** (A1) Was heißt „flüssig wie Blender“ (Pointer-Update, Klick-Aktion, Undo) und bei welcher **Bearbeitungsgröße** (20k oder 87,5k)? (A2) Wie viele Morph-Targets gleichzeitig (10 / 50 / 100)? (A3) Darf die Basis-Topologie gesperrt werden, solange Targets existieren? (A4) Sind UVs, Hard-Edges oder Split-Normalen geplant?
4. **Review und Entscheidung:** AD-022 und AD-023 brauchen je eine unabhängige Review in einer frischen Sitzung (AGENTS.md §6) und danach deine Entscheidung. Empfehlung des Agenten: beide gemeinsam entscheiden, weil sie sich bei der Zeilentabelle des Viewports berühren; erst danach der Prototyp (AD-023 §6).

## Grenzen dieser Aussagen

Nicht bewertet: GPU-Auswertung von Morph/Skin und ältere NumPy-Versionen auf dem Referenz-PC; Closest-Point-Snapping für Retopo; p95-Werte der Topologie-Operationen (n = 3); ob ein Journal in den Mesh-Primitiven lückenlos wäre. Retopo-Werkzeuge, Bevel, UV und Export existieren im Repo nicht.
