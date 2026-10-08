# Soft Selection (WP-SOFT-01 S1)

Headless experiment, Type B (Discovery), 2026-10-08. Question: what is the smallest semantic
model **primary selection → influence weights → transform** that holds path independence,
undo/cancel and stays cheap on real assets? This slice answers the technical questions so that a
later Production window slice (S2) can be planned on evidence. **No Production code changes,
no defaults chosen, no window/viewport.**

- Architecture frame: [`docs/architecture/V1_CORE.md`](../../docs/architecture/V1_CORE.md) §6
  (Soft Selection is not a selection mode; an influence map feeds operations).
- Core frozen, Soft Selection not part of Core V1:
  [`docs/architecture/CORE_V1_FREEZE.md`](../../docs/architecture/CORE_V1_FREEZE.md).
- Results and open questions: [`FINDINGS.md`](FINDINGS.md) (observations, no verdicts).

> **Imports nothing from `playground/`** (AD-010 precedent) and nothing from other experiments,
> guarded by `tests/test_import_boundary.py`. Reads `src/` (`core`, `mirai`) and
> `examples/loaders` only.

## Contents

| File | What it is |
|---|---|
| `influence.py` | `compute_influence(mesh, seeds, radius, metric, curve) -> {VertexId: w}`; metrics `euclidean` / `geodesic` (Dijkstra over edges, pruned at `r`), curves `smooth` / `linear`; `seeds_from_selection()` (= `resolve_selection_vertices`, V/E/F), `primary_pivot()` |
| `weighted_ops.py` | `SoftMoveOperation`, `SoftRotateOperation`, `SoftScaleOperation` — subclasses of the Core ops, taking `params["influence"]` (+ `params["pivot"]`, required for Rotate/Scale; `params["scale_formula"]` = `"linear"` / `"power"`); `soft_context()` builds the context from a `Selection` |
| `probe_cost.py` | CLI cost probe: two assets × radii 5/15/30 % of the bounding radius × both metrics |
| `_paths.py` | sys.path bootstrap (pattern copied from `symmetry_lab/_paths.py`) |
| `tests/` | experiment suite |

Weight rules (handoff E3–E6): `w = 1` on seeds, `0` at `d >= r`; Move `w·Δ`; Rotate `w·θ`
(weighted angle, not a position blend); Scale `1 + w·(F − 1)` per basis axis, or `F^w` for
comparison. Pivot only from the primary selection (E7). `params["symmetry"]` → `ValueError` (E9).

## Run

From the repo root (Windows command prompt / PowerShell and Linux alike):

```
python -m pytest experiments/soft_selection/tests
python experiments/soft_selection/probe_cost.py
python experiments/soft_selection/probe_cost.py --steps 200
python experiments/soft_selection/probe_cost.py --assets head_basemesh
python experiments/soft_selection/probe_cost.py --help
```

The probe needs no window and no `pyglet`. It prints machine information and one table per
asset (times in milliseconds, CPU side only — no viewport sync, no drawing).

## Praktischer Test für Manu (ca. 5 Minuten)

Es gibt noch nichts zu sehen — nur eine Messung auf deinem PC:

1. Eingabeaufforderung im Repo-Ordner öffnen.
2. `python experiments/soft_selection/probe_cost.py` ausführen.
3. Die Ausgabe (Tabelle mit Millisekunden) kopieren und in den Chat schicken.

Damit sehen wir, ob weiches Verschieben am Kopf und am Ganzkörper-Mesh auf deiner Hardware flüssig
bleiben kann.

## Next step

S2 (Production window slice) is planned from `FINDINGS.md` §5 (open questions) and the
reference-PC probe run. Nothing here is a promotion claim.
