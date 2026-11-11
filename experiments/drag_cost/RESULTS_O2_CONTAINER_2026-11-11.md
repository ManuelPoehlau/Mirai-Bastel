# O2 before / after in the container, 2026-11-11 (audit 2026-11-10 §H step 4)

**Container numbers, not the reference PC** (`docs/architecture/REFERENCE_HARDWARE.md` §4): Intel Xeon @ 2.10 GHz,
4 logical cores, Linux, Python 3.13.18, Mesa llvmpipe (software GL: draw times are CPU times, not GPU times). The
container was restarted once during the session; the second pair below ran back to back on one host and is the one to
read. Change: O2, face data without per-face vertex copies
([AD-018 addendum 2026-11-11](../../docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md)); report:
[audit addendum "O2 in the container"](../../docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md#addendum--o2-in-the-container-2026-11-11).

- "before" = `23faef5` (the D3 probe on the pre-O2 code; `src/` as `bc0f0b2`), run from a git worktree;
- "after" = `58f7052` (O2). Pair 1's "after" ran on the uncommitted first version of `_upload_face_normals` (same
  layout, an intermediate array per call; ~30 % slower in that function, measured in isolation on `gollum_20k`).

## D3 acceptance probe, `probe_d3_acceptance.py` (87.5k fixture, 15 % jaw region, Morph + Skin, complete frame)

Pair 2 (back to back, one host), p50 / p95 ms:

| Row | frame before | frame after | `_sync_geometry` before → after (p50) | face data → store before → after (p50) |
|---|---:|---:|---:|---:|
| pose, wire off | 225.90 / 289.78 | **198.91 / 245.10** | 138.94 → 102.34 | 42.51 → **10.73** |
| weight, wire off | 264.52 / 333.67 | **261.73 / 304.18** | 134.47 → 116.15 | 39.85 → **12.52** |
| pose, wire ON | 269.08 / 357.91 | **234.60 / 271.27** | 154.65 → 120.13 | 48.37 → **12.79** |
| weight, wire ON | 317.09 / 387.83 | **298.26 / 343.43** | 156.46 → 126.17 | 49.26 → **13.52** |

Bytes handed to the GL store per frame (every row, both pairs): **2,304,924 → 556,940** — face data 1,969,344 →
221,360 (−89 %), vertex data 335,580 unchanged; **176 → 42 bytes per region vertex**.

Pair 1 (the first "before" possibly on another host), frame p50 / p95, face data p50: pose off 204.09 / 280.15 →
166.50 / 235.86, 36.24 → 10.08; weight off 243.69 / 339.15 → 217.06 / 294.36, 36.68 → 10.98; pose ON 226.04 / 312.29 →
192.07 / 252.40, 37.65 → 10.11; weight ON 278.56 / 367.08 → 243.01 / 318.28, 40.59 → 10.99.

**Reading.** The face-data part of a deformation frame drops by a factor 3.5–4 and its bytes by 89 %; the frame by
about 25–40 ms p50 at 87.5k. Every row stays **OVER** the D3 bar (33.3 ms p95) before and after: what remains is
the per-vertex Python work O2 does not touch — stage evaluation 38–80 ms, face normals, vertex normals, neighbourhood
sets and position / normal mirrors ≈ 90 ms inside `_sync_geometry` — plus the llvmpipe draw. That is O1 / O3
territory (audit §G.3). The weight rows move least: their evaluation (mix + skin) is about twice the pose rows'.
Frame-to-frame noise in this container is large (p95 / p50 ≈ 1.2–1.4; whole rows shift 10–15 % between hosts); the
face-data rows and the byte counts are the stable result.

## Pose-step split, `probe_scale_audit.py --only split --assets dense --regions 15 --steps 30` (the audit's scenario)

Skin only (no morph target), `pointer_motion + update_viewport`, draw separate. Same host, back to back.

| p50 ms | before, wire off | after, wire off | before, wire ON | after, wire ON |
|---|---:|---:|---:|---:|
| step (p95) | 189.37 (237.01) | **137.49 (179.01)** | 169.25 (235.63) | **131.39 (183.15)** |
| 2 `_sync_geometry` | 146.88 | 96.60 | 130.59 | 86.20 |
| 2e face data → store | 46.57 (24.6 %) | **9.02 (6.6 %)** | 40.13 (23.7 %) | **8.26 (6.3 %)** |
| 4 face-data `glBufferSubData` at draw | 0.53 | 0.16 | 0.50 | 0.16 |
| draw + glFinish | 35.16 | 32.30 | 52.09 | 52.18 |
| bytes per step | 2,304,924 | **556,940** | 2,304,924 | **556,940** |

## Draw cost of the new fetches (llvmpipe only)

`gollum_87k`, 1024×768, 197,336 covered pixels, the production `GLRenderStore` and the frozen pre-O2 oracle
(`tests/gl_pre_o2_shading.py`) in one process, drawn alternately, 25 draws each after 3 warm-up, `render + glFinish`:

```
smooth: covered 197336 px; O2 median 49.39 ms (min 40.08); pre-O2 median 49.62 ms (min 38.38)
flat: covered 197336 px; O2 median 37.96 ms (min 30.64); pre-O2 median 37.34 ms (min 31.28)
```

No difference on llvmpipe. This says nothing about the GeForce 9800 GTX, where a Smooth-quad fragment now makes 27
texel fetches (24 single `R32F`) instead of 10 `RGBA32F`: measure there (commands below).

## Pixel identity

- `tests/test_gl_face_data_layout.py`: 16 scenes, production path vs the pre-O2 oracle, byte-identical; two shader
  mutations (wrong corner normal, `u_vertex_base` dropped) fail it.
- One-time cross-check against the real `bc0f0b2` tree (scratch script, each tree in its own process):
  `head_basemesh` and `gollum_20k` × Smooth / Flat × perspective / ortho × two views, Raitt light, default finish, a
  deformation of every fifth vertex through the patch path, 640×480 — **16 of 16 scenes byte-identical** (same covered
  pixel counts, 37,399–48,156 per scene).

## Tests (container)

- `xvfb-run -a python -m pytest tests/test_gl_*.py -q` (own process): **165 passed** (2 min 23 s).
- `xvfb-run -a python -m pytest tests -q`: **6,907 passed, 1 failed, 8 skipped, 66 subtests passed** (12 min 57 s). The
  failure is `tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring`, the "nicht committen" probe file that already
  failed before this change (audit §B, §I.7); untouched. The 8 skips are the GL modules inside a combined run (run
  separately above).
- `xvfb-run -a python -m pytest experiments/morph_lab/tests experiments/drag_cost/tests -q`: **129 passed**.
- Not run: `experiments/knife_oracle/tests` (no Knife or Core topology code changed).

## Commands for the reference PC (PowerShell, from the repo root)

GL tests in their own process — includes the pixel identity of O2 on the 9800 GTX driver:
```
python -m pytest (Get-ChildItem tests\test_gl_*.py) -q
```
D3 acceptance after O2 (prints the commit; about 2-4 minutes on the dense fixture):
```
python experiments\drag_cost\probe_d3_acceptance.py
```
D3 before O2, from a worktree of the probe commit on the pre-O2 code (delete it afterwards):
```
git worktree add ..\mirai-pre-o2 23faef5
Push-Location ..\mirai-pre-o2; python experiments\drag_cost\probe_d3_acceptance.py; Pop-Location
git worktree remove ..\mirai-pre-o2
```
The audit's pose-step split (compare with 391.73 ms p50, 87.5k 15 % wire off, after O0, 2026-11-11):
```
python experiments\drag_cost\probe_scale_audit.py --only split --assets dense --regions 15
```
GPU time of the shaded pass with the new fetches (compare the `gpu` column with 0.76 ms, orbit 87.5k, 2026-11-10):
```
python experiments\drag_cost\probe_navigation_gl.py --assets experiments\drag_cost\fixtures\gollum_87k.obj --scenarios orbit orbit_wire
```

## Raw outputs

### Pair 2, before (`23faef5`)
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 23faef5642, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on
  timed: GLRenderStore._flush_face_data, MixSurface._recompute, RenderMesh._sync_geometry, RenderMesh._upload_rows, SkinSurface._recompute, Viewport._sync_edges

  pose   wire off  frame  p50   225.90  p95   289.78  max   344.23 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.19  p95     0.27
    tick (update_viewport)                   p50   178.65  p95   239.32
    on_draw + glFinish                       p50    45.78  p95    58.54
      stage evaluation (mix + skin)          p50    35.47  p95    48.40
      RenderMesh._sync_geometry (all meshes) p50   138.94  p95   188.47
        of it: face data -> store            p50    42.51  p95    61.97
        face-data upload at draw             p50     1.51  p95     2.29
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

  weight wire off  frame  p50   264.52  p95   333.67  max   390.64 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.07  p95     0.10
    tick (update_viewport)                   p50   205.11  p95   272.65
    on_draw + glFinish                       p50    56.63  p95    65.69
      stage evaluation (mix + skin)          p50    64.65  p95    86.45
      RenderMesh._sync_geometry (all meshes) p50   134.47  p95   179.18
        of it: face data -> store            p50    39.85  p95    60.81
        face-data upload at draw             p50     1.49  p95     1.74
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

  pose   wire ON   frame  p50   269.08  p95   357.91  max   381.00 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.18  p95     0.23
    tick (update_viewport)                   p50   201.70  p95   273.38
    on_draw + glFinish                       p50    64.82  p95    85.38
      stage evaluation (mix + skin)          p50    41.00  p95    53.79
      RenderMesh._sync_geometry (all meshes) p50   154.65  p95   215.76
        of it: face data -> store            p50    48.37  p95    70.55
        face-data upload at draw             p50     1.54  p95     2.01
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

  weight wire ON   frame  p50   317.09  p95   387.83  max   418.12 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.08  p95     0.09
    tick (update_viewport)                   p50   231.79  p95   299.99
    on_draw + glFinish                       p50    81.06  p95    97.57
      stage evaluation (mix + skin)          p50    73.57  p95    88.29
      RenderMesh._sync_geometry (all meshes) p50   156.46  p95   201.47
        of it: face data -> store            p50    49.26  p95    69.92
        face-data upload at draw             p50     1.58  p95     2.72
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)
```

### Pair 2, after (`58f7052`)
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 58f7052d4e, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on
  timed: GLRenderStore._flush_face_data, MixSurface._recompute, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges

  pose   wire off  frame  p50   198.91  p95   245.10  max   248.89 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.19  p95     0.27
    tick (update_viewport)                   p50   150.13  p95   184.20
    on_draw + glFinish                       p50    48.65  p95    58.49
      stage evaluation (mix + skin)          p50    38.45  p95    49.64
      RenderMesh._sync_geometry (all meshes) p50   102.34  p95   133.07
        of it: face data -> store            p50    10.73  p95    14.32
        face-data upload at draw             p50     1.20  p95     2.67
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   261.73  p95   304.18  max   313.10 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.08  p95     0.10
    tick (update_viewport)                   p50   199.44  p95   233.71
    on_draw + glFinish                       p50    63.12  p95    72.91
      stage evaluation (mix + skin)          p50    75.05  p95    87.48
      RenderMesh._sync_geometry (all meshes) p50   116.15  p95   136.36
        of it: face data -> store            p50    12.52  p95    14.89
        face-data upload at draw             p50     1.16  p95     2.20
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   234.60  p95   271.27  max   275.45 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.19  p95     0.22
    tick (update_viewport)                   p50   162.96  p95   193.89
    on_draw + glFinish                       p50    74.28  p95    86.69
      stage evaluation (mix + skin)          p50    43.34  p95    49.97
      RenderMesh._sync_geometry (all meshes) p50   120.13  p95   138.62
        of it: face data -> store            p50    12.79  p95    15.72
        face-data upload at draw             p50     1.15  p95     1.60
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   298.26  p95   343.43  max   359.12 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.08  p95     0.11
    tick (update_viewport)                   p50   211.31  p95   243.51
    on_draw + glFinish                       p50    87.58  p95   101.65
      stage evaluation (mix + skin)          p50    80.07  p95    88.26
      RenderMesh._sync_geometry (all meshes) p50   126.17  p95   147.16
        of it: face data -> store            p50    13.52  p95    17.09
        face-data upload at draw             p50     1.22  p95     2.88
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### Pair 1, before (`23faef5`)
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 23faef5642, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on
  timed: GLRenderStore._flush_face_data, MixSurface._recompute, RenderMesh._sync_geometry, RenderMesh._upload_rows, SkinSurface._recompute, Viewport._sync_edges

  pose   wire off  frame  p50   204.09  p95   280.15  max   293.96 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.17  p95     0.23
    tick (update_viewport)                   p50   157.01  p95   231.60
    on_draw + glFinish                       p50    42.27  p95    54.98
      stage evaluation (mix + skin)          p50    33.35  p95    47.02
      RenderMesh._sync_geometry (all meshes) p50   116.10  p95   178.81
        of it: face data -> store            p50    36.24  p95    57.95
        face-data upload at draw             p50     1.45  p95     3.10
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

  weight wire off  frame  p50   243.69  p95   339.15  max   361.59 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.07  p95     0.09
    tick (update_viewport)                   p50   190.68  p95   275.48
    on_draw + glFinish                       p50    53.90  p95    68.21
      stage evaluation (mix + skin)          p50    61.24  p95    84.01
      RenderMesh._sync_geometry (all meshes) p50   117.95  p95   188.06
        of it: face data -> store            p50    36.68  p95    59.62
        face-data upload at draw             p50     1.44  p95     1.68
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

  pose   wire ON   frame  p50   226.04  p95   312.29  max   330.98 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.17  p95     0.23
    tick (update_viewport)                   p50   161.87  p95   235.13
    on_draw + glFinish                       p50    62.53  p95    83.96
      stage evaluation (mix + skin)          p50    34.68  p95    48.60
      RenderMesh._sync_geometry (all meshes) p50   121.44  p95   186.55
        of it: face data -> store            p50    37.65  p95    63.87
        face-data upload at draw             p50     1.47  p95     1.83
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

  weight wire ON   frame  p50   278.56  p95   367.08  max   396.43 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.07  p95     0.10
    tick (update_viewport)                   p50   207.94  p95   281.17
    on_draw + glFinish                       p50    72.37  p95    93.66
      stage evaluation (mix + skin)          p50    63.78  p95    85.31
      RenderMesh._sync_geometry (all meshes) p50   133.25  p95   187.49
        of it: face data -> store            p50    40.59  p95    62.87
        face-data upload at draw             p50     1.54  p95     3.14
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

real	1m31.800s
user	1m42.660s
sys	0m1.665s
```

### Pair 1, after (`23faef5` + the uncommitted first O2 version)
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 23faef5642, working tree MODIFIED
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on
  timed: GLRenderStore._flush_face_data, MixSurface._recompute, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges

  pose   wire off  frame  p50   166.50  p95   235.86  max   255.97 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.16  p95     0.21
    tick (update_viewport)                   p50   123.19  p95   176.67
    on_draw + glFinish                       p50    43.03  p95    57.61
      stage evaluation (mix + skin)          p50    32.29  p95    47.90
      RenderMesh._sync_geometry (all meshes) p50    83.78  p95   129.41
        of it: face data -> store            p50    10.08  p95    17.77
        face-data upload at draw             p50     1.12  p95     1.58
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   217.06  p95   294.36  max   305.86 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.07  p95     0.09
    tick (update_viewport)                   p50   161.64  p95   228.07
    on_draw + glFinish                       p50    53.72  p95    70.95
      stage evaluation (mix + skin)          p50    61.62  p95    83.96
      RenderMesh._sync_geometry (all meshes) p50    88.76  p95   136.02
        of it: face data -> store            p50    10.98  p95    18.05
        face-data upload at draw             p50     1.18  p95     1.41
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   192.07  p95   252.40  max   274.37 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.17  p95     0.23
    tick (update_viewport)                   p50   126.15  p95   186.51
    on_draw + glFinish                       p50    64.08  p95    79.12
      stage evaluation (mix + skin)          p50    33.51  p95    49.09
      RenderMesh._sync_geometry (all meshes) p50    85.12  p95   133.29
        of it: face data -> store            p50    10.11  p95    17.52
        face-data upload at draw             p50     1.06  p95     1.96
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   243.01  p95   318.28  max   338.83 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.07  p95     0.08
    tick (update_viewport)                   p50   164.95  p95   228.62
    on_draw + glFinish                       p50    71.33  p95    97.42
      stage evaluation (mix + skin)          p50    63.90  p95    87.40
      RenderMesh._sync_geometry (all meshes) p50    93.07  p95   134.17
        of it: face data -> store            p50    10.99  p95    19.02
        face-data upload at draw             p50     1.14  p95     1.73
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

real	1m22.027s
user	1m34.419s
sys	0m1.422s
```

### Split, before (`23faef5`)
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 30 pose steps, p50 ms
  step (pointer_motion + update_viewport)          189.37  100 %   (p95 237.01)
  1 skin evaluation (LBS + Mesh writes)             38.63   20.4 %
  2 RenderMesh._sync_geometry, total               146.88   77.6 %
  2a  neighbourhood sets                             9.89    5.2 %
  2b  face normals                                  33.11   17.5 %
  2c  vertex normals                                20.03   10.6 %
  2d  positions + normals -> mirror -> store        21.56   11.4 %
  2e  face rows (36 floats per face) -> store       46.57   24.6 %
  4 face-data glBufferSubData at draw                0.53    0.3 %
  draw + glFinish                                   35.16
  bytes handed to the store per step              2304924  (176 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 30 pose steps, p50 ms
  step (pointer_motion + update_viewport)          169.25  100 %   (p95 235.63)
  1 skin evaluation (LBS + Mesh writes)             33.60   19.9 %
  2 RenderMesh._sync_geometry, total               130.59   77.2 %
  2a  neighbourhood sets                             9.15    5.4 %
  2b  face normals                                  27.66   16.3 %
  2c  vertex normals                                14.36    8.5 %
  2d  positions + normals -> mirror -> store        17.97   10.6 %
  2e  face rows (36 floats per face) -> store       40.13   23.7 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                0.50    0.3 %
  draw + glFinish                                   52.09
  bytes handed to the store per step              2304924  (176 per weighted vertex)
```

### Split, after (`58f7052`)
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 30 pose steps, p50 ms
  step (pointer_motion + update_viewport)          137.49  100 %   (p95 179.01)
  1 skin evaluation (LBS + Mesh writes)             34.40   25.0 %
  2 RenderMesh._sync_geometry, total                96.60   70.3 %
  2a  neighbourhood sets                             9.52    6.9 %
  2b  face normals                                  30.04   21.8 %
  2c  vertex normals                                16.85   12.3 %
  2d  positions + normals -> mirror -> store        19.10   13.9 %
  2e  face data -> store (O2: face normals)          9.02    6.6 %
  4 face-data glBufferSubData at draw                0.16    0.1 %
  draw + glFinish                                   32.30
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 30 pose steps, p50 ms
  step (pointer_motion + update_viewport)          131.39  100 %   (p95 183.15)
  1 skin evaluation (LBS + Mesh writes)             34.41   26.2 %
  2 RenderMesh._sync_geometry, total                86.20   65.6 %
  2a  neighbourhood sets                            10.10    7.7 %
  2b  face normals                                  27.69   21.1 %
  2c  vertex normals                                14.07   10.7 %
  2d  positions + normals -> mirror -> store        16.76   12.8 %
  2e  face data -> store (O2: face normals)          8.26    6.3 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                0.16    0.1 %
  draw + glFinish                                   52.18
  bytes handed to the store per step               556940  (42 per weighted vertex)
```

### `tests/` summary
```
FAILED tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring - Assertion...
1 failed, 6907 passed, 8 skipped, 66 subtests passed in 777.77s (0:12:57)
```
