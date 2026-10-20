# Architecture audit probes (2026-10-20)

> Discovery probes for the viewport / mesh / workspace audit. They read the repository and change nothing; no GL, no
> window. Results feed the [audit summary](../../docs/research/viewport/ARCHITECTURE_AUDIT_2026-10-20.md) and its two
> detail reports. Not production code, not an architecture decision.

| Probe | Question | Run |
|---|---|---|
| `probe_mesh_cost.py` | What do `vertex_edges` (O(E)), `export_state`, `load_state`, the state comparison and one snapshot (= half an undo step) cost in time and memory on a dense mesh? | `python experiments/architecture_audit_probes/probe_mesh_cost.py [obj ...]` (default: `gollum_20k.obj`, `gollum.obj`) |
| `probe_morph_blend.py` | What does the blend arithmetic `base + sum(w_i * delta_i)` cost for N active morph targets (sparse / dense), in pure Python and with NumPy if importable, and how large are attribute layers (scalar mask, 4-influence weights) as `dict` vs `array`? Blend only: no normals, upload or draw. | `python experiments/architecture_audit_probes/probe_morph_blend.py [V]` |

## Result (container, 2026-10-20; **not** the reference PC)

Xeon @ 2.10 GHz, CPython 3.13, NumPy 2.5.3. Python-heavy code is about 2x slower on the reference PC
([`REFERENCE_HARDWARE.md`](../../docs/architecture/REFERENCE_HARDWARE.md) §2), the GL share more.

- `gollum_20k` (21 875 V): mesh + scene ~38 MB; one `export_state` snapshot ~31 MB (one undo step with before + after ~61 MB);
  `export_state` ~120 ms, `load_state` ~250 ms, `vertex_edges` ~2.5 ms per call. `gollum` (87 500 V): ~152 MB mesh; ~123 MB per
  snapshot (~246 MB per undo step); `export_state` ~600 ms, `load_state` ~2.1 s, `vertex_edges` ~10.7 ms. `HistoryStack` has no limit.
- Morph blend at 21 875 V, ms: pure Python, 15 % support: 1.5 / 14 / 65 for N = 1 / 10 / 50; fully populated: 7.1 / 62 / 373;
  NumPy fully populated: 0.05 / 0.15 / 0.37. Attribute layer for 21 875 V: scalar as `dict` 2.5 MB, as `array('f')` 0.09 MB; skin
  weights with 4 influences as nested dicts 9 MB, copied into every full snapshot.

Open on the reference PC: whether NumPy imports on the Q9550 (SSE4.1, no SSE4.2/AVX) and what these rows cost there
([audit 2](../../docs/research/viewport/ARCHITECTURE_AUDIT_2026-10-20_FUTURE_REQUIREMENTS.md), plan step P0).
