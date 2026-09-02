# Viewport V1 — Performance Research / Profiling

Experimenteller Benchmark- und Instrumentationsbereich für die Frage:

> Warum wird der Viewport V1 bereits bei 326 Vertices / 324 Quads spürbar langsam?

**Regeln dieses Bereichs:**

- Nur Messung und Analyse. **Keine Optimierung**, keine Änderung an
  Viewport-, Core- oder Topology-Dateien.
- Die Instrumentation arbeitet ausschließlich per Monkey-Patching auf
  Fensterinstanzen (`perf_probe.instrument_window`) — bestehender Code bleibt
  unberührt.
- Ergebnisse und Befunde: [`PERF_BASELINE_REPORT.md`](PERF_BASELINE_REPORT.md)

## Aufbau

```text
perf_probe.py       Timing-/Zähler-Instrumentation (Monkey-Patching, GC-Snapshot)
scenario_runner.py  Szenarien A-H am echten Fenster mit dem echten Head-Basemesh
micro_bench.py      headless CPU-Mikrobenchmarks (Picking, Normalen, Arrays, Allokationen)
synthetic_meshes.py Quad-Torus-Generator (~324 / ~1.3k / ~5k / ~20k Quads)
bench_scaling.py    Skalierung Orbit+Hover über Mesh-Größen (echtes Fenster, echtes GL)
profile_hotspots.py cProfile der gemischten Interaktionslast (Hotspot-Nachweis)
bench_live.py       Live-Instrumentation für manuelle Interaktion (echter Head-Viewport)
```

## Ausführung

Alle Aufrufe aus `experiments/mirai_bastel_viewport_V1` (Repo-.venv mit pyglet 2.1):

```bash
python -m perf.micro_bench          # headless, kein Fenster, einige Minuten
python -m perf.scenario_runner --events 200    # öffnet ein Fenster mit dem Head
python -m perf.bench_scaling --events 50 --budget 20   # Skalierungstabelle
python -m perf.profile_hotspots     # cProfile-Toplisten
python -m perf.bench_live           # manueller Test mit Live-Report (5 s Intervall)
```

`scenario_runner`/`bench_scaling`/`bench_live` öffnen ein echtes
pyglet-Fenster (echter GL-Kontext, echte VertexList-Uploads); VSync ist für
CPU-Kostenmessung bewusst aus. Windows-Konsole ggf. mit
`set PYTHONIOENCODING=utf-8` starten.

## Methodik (reproduzierbar)

- Events werden direkt an die echten Event-Handler des Fensters geliefert
  (gleiche Technik wie `_smoke_all_tools.py` und die headless-Tests) —
  kein Maus-Automations-Framework.
- Ein "Frame" = ein Event + ein `on_draw()`; gemessen wird die Framezeit
  (avg/p50/p95/p99/max) plus Komponenten (picking / rebuild /
  normals / triangle-arrays / GL-VertexList / draw).
- Szenarien: Idle, Orbit, Pan, Zoom, Hover (über dem Mesh), Hover-still,
  Vertex-/Edge-/Face-Selection+Drag — siehe Task-Spezifikation.
- Micro-Benchmarks spiegeln den exakten Algorithmus von `app.py`
  (`_compute_normals`, `_face_triangle_arrays`) ohne GL-Anteil nach.

## Ergebnisse

Aktuelle Messungen und Befund: [`PERF_BASELINE_REPORT.md`](PERF_BASELINE_REPORT.md)
(inkl. Rohdaten: `micro_bench_results.txt`, `scaling_results.txt`,
`profile_results.txt`, `scenario_results.txt`).
