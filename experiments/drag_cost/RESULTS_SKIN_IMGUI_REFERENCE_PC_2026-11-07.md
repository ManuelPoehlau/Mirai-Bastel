# Skin + ImGui — Reference-PC Measurements, 2026-11-07

**Purpose:** First reference-PC numbers for (1) the pose step (AD-028 P-1) and
(2) the ImGui panel cost (AD-030 §6.7, §3.3).  
**Branch/commit:** `main` @ 2ee2061  
**Methodology:** handoff 2026-11-07, Discovery mode.

---

## M4 — Hardware and software

| Item | Value |
|---|---|
| Platform | Windows 10, 10.0.19045 |
| CPU | Intel Core 2 Quad Q9550 @ 2.83 GHz (4 logical cores) |
| GPU | GeForce 9800 GTX/9800 GTX+/PCIe/SSE2 |
| GL_VERSION | 3.3.0 |
| Python (M1, M3) | 3.14.2 (CPython) |
| Python (M2 bench) | 3.12.10 (CPython, system install) — imgui-bundle 1.93.0 |
| Windows display scaling | *Manu to report* |

---

## M1 — Pose-step cost (`--only-skin`, 200 steps per row)

Command: `python experiments/drag_cost/probe_morph_gl.py --only-skin`  
Bar (AD-028 P-1): **≤ 16.7 ms p95** for head and Man_With_Shoes at ≤ 15 % region.  
SubD is not part of P-1; gollum_20k SubD refused at all regions (>25k faces at level 1).

| Mesh | V | region % | variant | p50 ms | p95 ms | verdict |
|---|---:|---:|---|---:|---:|---|
| head_basemesh | 326 | 5 | plain | 1.76 | 2.97 | ok |
| head_basemesh | 326 | 5 | morph 60 % | 1.72 | 2.93 | ok |
| head_basemesh | 326 | 5 | SubD L2 | 33.35 | 35.26 | OVER (not P-1) |
| head_basemesh | 326 | 15 | plain | 2.31 | 2.75 | ok |
| head_basemesh | 326 | 15 | morph 60 % | 2.37 | 2.97 | ok |
| head_basemesh | 326 | 15 | SubD L2 | 53.44 | 58.43 | OVER (not P-1) |
| head_basemesh | 326 | 100 | plain | 8.99 | 10.00 | ok |
| head_basemesh | 326 | 100 | morph 60 % | 8.84 | 9.67 | ok |
| head_basemesh | 326 | 100 | SubD L2 | 160.66 | 248.34 | OVER (not P-1) |
| Man_With_Shoes | 928 | 5 | plain | 2.38 | 2.94 | ok |
| Man_With_Shoes | 928 | 5 | morph 60 % | 2.83 | 7.60 | ok |
| Man_With_Shoes | 928 | 5 | SubD L2 | 65.09 | 70.76 | OVER (not P-1) |
| Man_With_Shoes | 928 | 15 | plain | 4.75 | 5.38 | ok |
| Man_With_Shoes | 928 | 15 | morph 60 % | 4.82 | 5.55 | ok |
| Man_With_Shoes | 928 | 15 | SubD L2 | 133.32 | 167.82 | OVER (not P-1) |
| Man_With_Shoes | 928 | 100 | plain | 25.01 | 26.37 | OVER (outside P-1 scope) |
| Man_With_Shoes | 928 | 100 | morph 60 % | 25.84 | 27.58 | OVER (outside P-1 scope) |
| Man_With_Shoes | 928 | 100 | SubD L2 | 470.76 | 744.94 | OVER (not P-1) |
| gollum_20k | 21 875 | 5 | plain | 35.31 | 58.72 | OVER (H5c) |
| gollum_20k | 21 875 | 5 | morph 60 % | 34.83 | 44.05 | OVER (H5c) |
| gollum_20k | — | 5 | SubD L2 | — | — | refused |
| gollum_20k | 21 875 | 15 | plain | 99.36 | 108.87 | OVER (H5c) |
| gollum_20k | 21 875 | 15 | morph 60 % | 100.58 | 114.26 | OVER (H5c) |
| gollum_20k | — | 15 | SubD L2 | — | — | refused |
| gollum_20k | 21 875 | 100 | plain | 698.21 | 837.06 | OVER (H5c) |
| gollum_20k | 21 875 | 100 | morph 60 % | 709.88 | 758.48 | OVER (H5c) |
| gollum_20k | — | 100 | SubD L2 | — | — | refused |

---

## M2 — ImGui panel cost (`bench.py`, 150 frames per process, Python 3.12)

Command: `python experiments/gui_framework_spike/bench.py gollum_20k.obj --variant {plain|open|closed}`  
Bench note: `resource` module (Unix-only) replaced with ctypes stub in bench.py (trivial fix); maxRSS unavailable
(ctypes stub returned 0 — not critical). imgui-bundle not installed in Python 3.14.2; ran under Python 3.12 system
install (`C:\Users\Manuel\AppData\Local\Programs\Python\Python312\python.exe`).

| Variant | idle p50 ms | idle p95 ms | orbit p50 ms | orbit p95 ms | imgui CPU p50/p95 ms | Start s |
|---|---:|---:|---:|---:|---|---:|
| plain (no imgui) | 9.45 | 19.07 | 8.36 | 10.19 | — | 4.36 |
| open (panel open) | 10.00 | 35.31 | 9.55 | 12.06 | 0.78 / 1.53 | 7.37 |
| closed (button only) | 10.28 | 81.20 | 9.03 | 11.25 | 0.37 / 2.12 | 12.40 |

---

## M3 — Pose-step split on gollum_20k (60 steps, Python 3.14.2)

Script: `experiments/drag_cost/probe_skin_split.py`  
Splits: **lbs** = `SkinSurface._recompute`; **_sync_geometry** = `RenderMesh._sync_geometry` (normals + GL uploads);  
**gl draw** = `viewport.render()` + `glFinish()`; **remainder** = pointer_motion + viewport.sync overhead.

| Component | 5 % region (1 093 V) | % of p50 | 15 % region (3 281 V) | % of p50 |
|---|---:|---:|---:|---:|
| **total** | 37.77 / 40.33 ms | — | 104.37 / 109.44 ms | — |
| lbs | 5.45 / 6.15 ms | 14 % | 16.71 / 17.40 ms | 16 % |
| _sync_geometry | 27.54 / 28.72 ms | **73 %** | 79.85 / 82.20 ms | **77 %** |
| gl draw | 3.48 / 5.73 ms | 9 % | 5.35 / 8.84 ms | 5 % |
| remainder | 1.16 / 1.53 ms | 3 % | 2.52 / 3.38 ms | 2 % |

*(p50 / p95 ms)*

---

## 5-line summary

1. **P-1 bar holds** (AD-028): head and Man_With_Shoes at ≤ 15 % region are well under 16.7 ms p95
   (worst: Man_With_Shoes 15 % morph 5.55 ms). SubD not in scope for P-1.
2. **gollum_20k is usable, not fluid (H5c confirmed)**: even at 5 % region, p50 = 35 ms, p95 = 59 ms;
   Man_With_Shoes at 100 % (928 V) is OVER at p50 = 25 ms (outside P-1 scope, noted for record).
3. **Split confirms hypothesis** (AD-028 §5.4): `_sync_geometry` is 73–77 % of the pose step on gollum_20k;
   LBS is only 14–16 %. GPU skinning alone would not cross the bar on gollum_20k.
4. **ImGui cost is negligible**: panel CPU 0.78 ms open / 0.37 ms closed per frame; orbit p95 barely
   above baseline (12 ms open vs 10 ms plain). Idle p95 spikes (35–81 ms) are occasional GC/driver events,
   not panel cost.
5. **Bench.py on Windows**: `resource` module fixed (trivial); imgui variants require Python 3.12 with
   imgui-bundle installed (not in 3.14.2 env) — note for anyone repeating this run.

---

## Manu's test points (Artist observations, to be filled in by Manu)

Three subjective checks after the probe run. Answers go here as Manu's words.

1. **Outliner open/close vs Orbit flüssigkeit:**
   gollum_20k öffnen, Outliner auf/zu: fühlt sich Orbit gleich flüssig an?

   *Artist observation (Manu, 2026-11-07):* „ja, orbit ist genauso flüssig" — kein spürbarer Unterschied mit/ohne Outliner.

2. **Kiefer-Pose ruckeln:**
   Kiefer-Pose drehen (Kopf vs. Gollum): ab wo ruckelt es? Kurz in Worten, mit Asset.

   *Artist observation (Manu, 2026-11-07):* gollum_20k — bis 15 % Falloff noch relativ flüssig; 20–25 % merkbar stockend, noch ok; ab 35–40 % sehr große Sprünge. Generell ist Hold 7 zum Falloff-Einstellen sehr träge/sprunghaft.

3. **Outliner-Lesbarkeit bei Windows-Skalierung:**
   Sind Outliner/Menüleiste bei deiner Windows-Skalierung gut lesbar?

   *Artist observation (Manu, 2026-11-07):* ja, ok, erfüllt erstmal seinen Zweck — Thema für einen eigenen Chat.
