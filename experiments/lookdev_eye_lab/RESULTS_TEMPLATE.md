# Lookdev P1 Eye Proof — results, <MACHINE>, <DATE>

Copy to `RESULTS_<MACHINE>_<DATE>.md`. Every cell carries a label: **MEASURED [RPC]** / **MEASURED [MAIN]** /
**TESTED [C]** / **OPEN**; **[H]** marks a reading of the numbers. Commands: [README.md](README.md).

## Kurzfassung für Manu (Deutsch)

- …

## 1. Run record

| Field | Value |
|---|---|
| Machine | |
| Interpreter, numpy, pyglet | |
| Commit / `src/` tree (`Source:` line) | |
| GL version / renderer / context | |
| `EVIDENCE:` line | |
| NVIDIA power setting | |
| Lab tests (`pytest experiments\lookdev_eye_lab\tests`) | |

## 2. Probe verdicts

| Check | Result | Label |
|---|---|---|
| [E] RGBA16F / RGBM8 upload 64 / 128 / 256, driver format, memory | | |
| [E] prefilter time per chain (CPU) | | |
| [S] seams of the lab chain (to 2², corners equalized), seamless on; raw chain for comparison | | |
| [Q5] `GL_SRGB8_ALPHA8` decode vs the shader decode | | |
| [P] parity, 11 functions | | |
| [V] every variant: GL errors none, image differs from T-A | | |
| [W] roughness sweep monotonic (T-C, T-D) | | |
| [R] hygiene | | |

## 3. GPU time per frame (clear + background + eye), eye ≈ 50 % of the frame, ms p50 / p95

| Variant | 1024×768 front | ¾ | profile | 1920×1080 front | ¾ | profile |
|---|---|---|---|---|---|---|
| T-A C1 | | | | | | |
| T-A C2 (Ghost) | | | | | | |
| T-B C1 / C2 / C3 | | | | | | |
| T-C C1 / C2 / C3 | | | | | | |
| T-D C1 / C2 / C3 | | | | | | |
| background alone | | | | | | |

## 4. Artist verdict (Manu): KEEP / ITERATE / REJECT

Criteria (audit §5.5): 1 crisp softbox reflection that reads "wet" · 2 Fresnel visible · 3 roughness reads (sclera
soft, cornea sharp) · 4 iris readable through the cornea · 5 no seams, flicker noted · 6 C1 alone reads as a wet eye.

| | C1 | C2 | C3 | Notes (views, orbit, flicker) |
|---|---|---|---|---|
| T-A | | | — | |
| T-B | | | | |
| T-C | | | | |
| T-D | | | | |

| Also | Verdict / note |
|---|---|
| LOD mapping linear vs sqrt (chrome sweep `G`) | |
| RGBA16F vs RGBM8 (`F`) | |
| clamp vs Reinhard (`T`) | |
| background solid vs environment (`B`) | |
| defaults: sclera roughness 0.30, cornea 0.04, exposure 0 EV, key 3.0 | |

## 5. Reading for D-L3, D-L6 … D-L8

- …

## 6. Raw output

```
<paste>
```
