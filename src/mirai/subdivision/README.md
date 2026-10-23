# SubD in Production (`src/mirai/subdivision/`)

**Status (2026-10-23):** Production-Fähigkeit, **nicht Artist-validiert**. Gebaut, automatisch getestet und im
Container gemessen. Die Richtung hat Manu freigegeben ("SubD gehört in den Production-Modeller", Käfig, Isolinien und
Highlight als eine zusammenhängende Darstellung); Tasten, Stufen-Default, Limit und Look sind `PROVISIONAL`.
Herkunft: das SubD Lab ([`experiments/subdivision_lab/`](../../../experiments/subdivision_lab/README.md),
WP-SUBD-LAB-01/02) — der Evaluator ist von dort **verschoben**, nicht kopiert; das Lab nutzt jetzt diesen Code.

## Für Manu (Deutsch)

Start wie immer: `python src/main.py` (Kopf) oder `python src/main.py subd_cube`. SubD ist beim Start aus.

| Taste (`PROVISIONAL`, Kontext `subd`) | Wirkung |
|---|---|
| `V` | aus → glatte Fläche + Käfig → glatte Fläche + Isolinien → aus |
| `Strg+1` / `Strg+2` / `Strg+3` | Stufe 1 / 2 / 3 (Start: 2) |
| `Shift+V` | Käfig: von der glatten Fläche verdeckt (Start) ↔ immer sichtbar |

Alles andere ist die App: Auswahl, `W`/`E`/`R`, Tweak, Soft Selection, `C`/Knife, `T`, Löschen/Auflösen, Symmetrie,
Undo/Redo, `D`/`Strg+D`. Bearbeitet wird immer der Käfig (das Control-Mesh); die glatte Fläche folgt live.
Die SubD-Tasten ändern nur die Ansicht: kein Undo-Schritt, nichts wird in der Szene gespeichert. Während `W`/`E`/`R`/`T`
gehalten wird oder der Knife läuft, werden sie sichtbar abgelehnt. In einer symmetrischen Knife-Sitzung bleibt `V` die
Spiegel-Variante des Knife.

Wenn das Mesh nicht unterteilt werden kann (z. B. ein Vertex, an dem sich zwei Löcher berühren), zeigt der Viewport
wieder den Käfig und die Statuszeile sagt `SubD aus: …` mit dem Grund; sobald die Topologie wieder passt (oder nach
Undo), ist die Fläche wieder da.

## For agents (English)

- **Ownership.** `Application.subdivision` (`preview.SubdivisionPreview`) owns view, level and line settings (transient,
  no document state, no History — research OF-3 stays open). The Viewport knows no subdivision: the surface goes through
  the replacement-surface hook (AD-013 H7, `Viewport.set_surface_provider`), the lines through an extra overlay (H1).
  Both are attached only while the preview is on (H7-R1 as amended 2026-10-23: inert without SubD), and never over another
  host's provider (H7-R4; the Morph Lab keeps its slot).
- **Evaluator boundary.** `catmull_clark.py`: `SubdSurface(mesh).level(n)` → `SubdLevel` (faces, composed stencils,
  inverse index, provenance, isolines with their control edge, stable keys). Nothing else knows Catmull-Clark; an
  alternative evaluator (OpenSubdiv) replaces this module behind the same data. Pure Python, no NumPy.
- **Updates** (`SubdSurfaceProvider`, reads the control mesh's change journal `Mesh.watch()`): nothing recorded → no work;
  positions only → `apply_local` per moved control vertex (> 12.5 % moved: `apply_full`), the viewport patches the moved
  derived vertices; edges/faces touched or vertices created/removed → topology + stencils rebuilt (global index data),
  the derived mesh **patched in place** by stable keys (`surface_topology_changed`, the surface `RenderMesh` patches its
  topology incrementally, AD-023); level switch / other edit object / first build → fresh derived mesh. Shift+S alone
  (definition only) rebuilds nothing.
- **Unsupported topology** (`SubdUnsupportedError`: edge with > 2 faces, loose edge/vertex, boundary vertex without
  exactly two boundary edges, non-fan vertex): `surface_mesh = None` (the viewport draws the cage's faces), status
  `SubD aus: …`; edits, picking and History continue on the cage; the next topology change retries.
- **Limits** (`PROVISIONAL`): levels 1–3, `MAX_DERIVED_FACES = 25 000`. Face counts: `subd_cube` (24 quads)
  96 / 384 / 1 536; `head_basemesh` 1 296 / 5 184 / 20 736; `man_with_shoes_basemesh` 3 704 / 14 816 / 59 264
  (level 3 refused). A topology change that pushes the shown level over the limit falls back to the highest allowed level.
- **Keys:** `preview.SUBD_KEYS`, binding context `subd` (`interaction.input.SUBD_CONTEXT`), installed in
  `Application.__init__` with a conflict check against the default contexts (`SubdBindingConflict`); resolved by
  `Application.key_press` only when the global context leaves the input unbound, so an app key or a user `keymap.json`
  binding always wins; `keymap.json` may rebind them in context `subd`.
- **Out of scope:** creases, adaptive subdivision, limit-surface normals, picking on the surface, Multires, OpenSubdiv.

## Measurements (container only — not the reference PC)

`xvfb-run -a python experiments/subdivision_lab/probe_app.py` (2026-10-23, cloud container, Xvfb + llvmpipe, 1280×800
hidden window; median / p95 ms per W-drag move of one vertex, 60 moves). *provider* = journal + stencils + derived mesh
writes (evaluator side), *upload* = the surface `RenderMesh.sync` (GPU buffer patches), *sync* = the whole
`Viewport.sync`, *frame* = `render()` + `glFinish()` on a software rasteriser.

| asset | level | faces | provider | upload | sync | frame | topology edit (split one edge, whole step incl. frame) |
|---|---:|---:|---:|---:|---:|---:|---:|
| head_basemesh | 1 | 1 296 | 0.10 / 0.17 | 0.73 / 1.14 | 1.48 / 2.25 | 6.2 / 8.3 | 39 ms |
| head_basemesh | 2 | 5 184 | 0.72 / 0.96 | 2.74 / 4.61 | 4.21 / 6.61 | 9.5 / 12.2 | 336 ms |
| head_basemesh | 3 | 20 736 | 2.55 / 4.57 | 10.2 / 17.7 | 13.6 / 22.7 | 18.2 / 21.5 | 928 ms |
| man_with_shoes_basemesh | 1 | 3 704 | 0.10 / 0.14 | 0.56 / 0.79 | 2.01 / 2.69 | 8.3 / 10.3 | 113 ms |
| man_with_shoes_basemesh | 2 | 14 816 | 0.40 / 0.60 | 1.63 / 2.62 | 3.08 / 4.79 | 14.1 / 18.9 | 487 ms |

A topology edit is dominated by the global stencil rebuild (head level 3: ≈ 0.5–0.6 s of the 0.93 s); before the in-place
patch the same edit cost 2.3 s (a fresh derived mesh + a structural GPU rebuild). The Lab's standalone bench
(`bench.py`, M1–M8/D1) on the same container: head level 3 drag step D1 18.5 ms median (the Lab's 2026-10-02 run measured
2 845 ms, before the 2026-10-10 slice-patch fix in `GLRenderStore`). Reference-PC rule of thumb from
`docs/architecture/REFERENCE_HARDWARE.md` (Python ≈ 2×, frame 1.6–2.2× the container) is an estimate, not a measurement.

## Tests

`tests/test_subdivision_exact.py`, `tests/test_subdivision_stencils.py`, `tests/test_subdivision_unsupported.py`
(evaluator: exact values, stencils = an independent recursive Catmull-Clark, local = full, provenance, unsupported input;
moved from the Lab), `tests/test_subdivision_app.py` (app path: keys, levels, W/E/R, Tweak, Soft, symmetry, Extrude,
Connect/Split, Knife, Dissolve, Delete, unsupported fallback, Undo/Redo, in-place patch, scene load, foreign provider),
`tests/test_subdivision_import_boundary.py` (nothing from `experiments/` or `playground/`).
