# Lookdev GPU probe — results, <MACHINE>, <YYYY-MM-DD>

<!-- Copy to RESULTS_<RPC|MAIN|CONTAINER>_<YYYY-MM-DD>.md. Every value cell carries its evidence label. A cell for a
machine that did not run stays OPEN: never fill a reference-PC or main-PC cell from a container run, and never infer a
PASS from the OpenGL specification. -->

**Evidence labels:** **MEASURED [RPC]** = run on the reference PC · **MEASURED [MAIN]** = run on the main PC ·
**TESTED [C]** = run only in a container / development environment (software renderer: no statement about a GPU
driver, timer is not a GPU timer) · **OPEN** = not run or inconclusive.
**Commands:** [README.md](README.md) ("Commands — reference PC" / "main PC").

## Run record (one block per machine that ran)

| Field | Value |
|---|---|
| Machine | RPC / MAIN / container |
| Date, who ran it | |
| Commit (`Source:` line) | |
| `src/` tree (`Source:` line, or `git rev-parse --short=10 HEAD:src`) | |
| Working tree | clean / MODIFIED (+ on-disk `src/` tree) |
| Python, numpy, pyglet, interpreter path | |
| OS (`Platform:`), CPU | |
| GL_VERSION / GL_RENDERER / GL_VENDOR / GLSL | |
| Context profile, flags | |
| `EVIDENCE:` line | hardware renderer / SOFTWARE RENDERER |
| GPU driver version (NVIDIA control panel → System information; the probe cannot read it) | |
| NVIDIA power management "prefer maximum performance" set (global)? | yes / no / unknown |
| Screens, window scale / dpi (probe line `Window …`) | |

## Limits and extensions

| Item | RPC | MAIN | C |
|---|---|---|---|
| GL_MAX_TEXTURE_IMAGE_UNITS | OPEN | OPEN | OPEN |
| GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS | OPEN | OPEN | OPEN |
| GL_MAX_TEXTURE_SIZE | OPEN | OPEN | OPEN |
| GL_MAX_CUBE_MAP_TEXTURE_SIZE | OPEN | OPEN | OPEN |
| GL_MAX_SAMPLES | OPEN | OPEN | OPEN |
| GL_MAX_COLOR_ATTACHMENTS / GL_MAX_DRAW_BUFFERS | OPEN | OPEN | OPEN |
| GL_MAX_TEXTURE_BUFFER_SIZE / GL_MAX_RENDERBUFFER_SIZE | OPEN | OPEN | OPEN |
| GL_MAX_TEXTURE_MAX_ANISOTROPY | OPEN | OPEN | OPEN |
| `GL_EXT_texture_filter_anisotropic` | OPEN | OPEN | OPEN |
| `GL_NVX_gpu_memory_info` (+ dedicated / total / current available KiB) | OPEN | OPEN | OPEN |
| `GL_ARB_seamless_cube_map` | OPEN | OPEN | OPEN |
| other Lookdev-relevant extensions (probe list) | OPEN | OPEN | OPEN |
| read-back target `RGBA32F` colour renderbuffer complete | OPEN | OPEN | OPEN |

## Capability checks

| Check | Format | RPC | MAIN | C | Notes (driver-reported format, max error, memory drop, GL errors) |
|---|---|---|---|---|---|
| A allocation + sampling, 64²–512² | RGBA8 | OPEN | OPEN | OPEN | |
| | RGBA16F (half data) | OPEN | OPEN | OPEN | |
| | RGBA16F (float data) | OPEN | OPEN | OPEN | |
| | RGBA32F | OPEN | OPEN | OPEN | |
| B `textureLod` explicit levels | RGBA8 | OPEN | OPEN | OPEN | |
| | RGBA16F | OPEN | OPEN | OPEN | |
| | RGBA32F | OPEN | OPEN | OPEN | |
| C bilinear (error in texel steps) | RGBA8 | OPEN | OPEN | OPEN | |
| | RGBA16F | OPEN | OPEN | OPEN | |
| | RGBA32F | OPEN | OPEN | OPEN | |
| C trilinear (error in level steps, monotonic) | RGBA8 | OPEN | OPEN | OPEN | |
| | RGBA16F | OPEN | OPEN | OPEN | |
| | RGBA32F | OPEN | OPEN | OPEN | |
| D seams (on continuous / off = predicted clamp seam) | RGBA8 | OPEN | OPEN | OPEN | |
| | RGBA16F | OPEN | OPEN | OPEN | |
| | RGBA32F | OPEN | OPEN | OPEN | |
| D seam panoramas looked at (`out/seams_*.png`) | — | OPEN | OPEN | OPEN | |
| R resources released, state restored, `glGetError` clean | — | OPEN | OPEN | OPEN | |
| Lab tests (`pytest experiments\lookdev_gpu_probe\tests`) | — | OPEN | OPEN | OPEN | |

## T — full-frame cube fetch cost (GL_TIME_ELAPSED p50 ms, cost over the no-fetch baseline in brackets)

Cube 128² + mips, 1 `textureLod` per fragment, 100 % coverage. Container values are not GPU times.

| Variant | 1024×768 RPC | 1024×768 MAIN | 1920×1080 RPC | 1920×1080 MAIN |
|---|---|---|---|---|
| no fetch (baseline) | OPEN | OPEN | OPEN | OPEN |
| RGBA8 sharp (lod 0), seamless off / on | OPEN | OPEN | OPEN | OPEN |
| RGBA8 rough (lod 4.5), seamless off / on | OPEN | OPEN | OPEN | OPEN |
| RGBA16F sharp, seamless off / on | OPEN | OPEN | OPEN | OPEN |
| RGBA16F rough, seamless off / on | OPEN | OPEN | OPEN | OPEN |
| RGBA32F sharp, seamless off / on | OPEN | OPEN | OPEN | OPEN |
| RGBA32F rough, seamless off / on | OPEN | OPEN | OPEN | OPEN |
| NOTE (times spread > 2.5×) printed? | OPEN | OPEN | OPEN | OPEN |

## Worklight baseline — `drag_cost/probe_shading_gpu.py` (unchanged; GPU p50 ms per face-data variant)

Fixture `gollum_87k` (87,500 V / F), Smooth, framed view. `image vs o2` must be `identical` for `pre-o2` and `o2-rgba`.

| Size (framebuffer printed) | Covered px (%) | `off` | `pre-o2` | `o2` (production) | `o2-rgba` | Image check | Label |
|---|---|---|---|---|---|---|---|
| 1024×768 | | | | | | | OPEN |
| 1920×1080 | | | | | | | OPEN |

## Worklight at close-up coverage — `probe_worklight_coverage.py` (GPU p50 ms)

| Size | Dolly | Coverage | `off` | `pre-o2` | `o2` | `o2-rgba` | Image check | Label |
|---|---|---|---|---|---|---|---|---|
| 1024×768 | 1.0 | | | | | | | OPEN |
| 1024×768 | 0.5 | | | | | | | OPEN |
| 1024×768 | 0.3 | | | | | | | OPEN |
| 1920×1080 | 1.0 | | | | | | | OPEN |
| 1920×1080 | 0.5 | | | | | | | OPEN |
| 1920×1080 | 0.3 | | | | | | | OPEN |

Consistency: the dolly-1.0 rows must match the plain `probe_shading_gpu.py` rows of the same size within
run-to-run variation; if not, the coverage runs are not comparable.

## Reading for the Eye Proof (P1)

| Question | Answer | Label |
|---|---|---|
| Environment format P1 starts from (RGBA16F / RGBA8 + RGBM / other) | | OPEN |
| Seamless filtering usable, or CPU edge fix-up of the prefiltered mips needed | | OPEN |
| `textureLod` by roughness usable (B, C trilinear) | | OPEN |
| Cost of one environment fetch at full frame (T, rough, seamless on) vs the frame budget (16.7 / 33.3 ms) | | OPEN |
| Worklight pass at a full-frame close-up (o2, dolly 0.3) — the budget left for Lookdev shading | | OPEN |
| Fallback tier needed on this machine (T-D analytic softbox, lower environment size) | | OPEN |

## Raw output

```
<paste: version / commit lines>
```

```
<paste: probe_gl_caps.py>
```

```
<paste: probe_shading_gpu.py, 1024x768>
```

```
<paste: probe_shading_gpu.py --size 1920 1080>
```

```
<paste: probe_worklight_coverage.py, 1024x768>
```

```
<paste: probe_worklight_coverage.py --size 1920 1080>
```
