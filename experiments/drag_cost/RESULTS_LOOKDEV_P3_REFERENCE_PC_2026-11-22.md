# LookDev P3-0 probe — reference PC, runs 1–5 (Manu, 2026-11-22): complete

`python experiments\drag_cost\probe_lookdev.py --p3` ([AD-039](../../docs/architecture/AD-039-LOOKDEV-P3.md) §11.1).
Q9550, GeForce 9800 GTX+ (512 MiB), GL 3.3.0, Python 3.12.10, Windows 10; source "commit unknown (no git)" (the
probe file is the one of commit `643d0f4`: the traceback's line numbers match it).

## Outcome

Both processes (1024×768, 1920×1080) finished section (p3a) and then **stopped in the first (p3c) frame rows** with
`GLException (0x1285): Out of memory` raised by `glDrawElements` of the skin stand-in (`Frames.lookdev`). The (p3b)
cube lines and every frame row were collected and lost with the exception (the probe printed a section only at its
end). Which row failed is therefore **not known**.

Changed in the probe the same day (run 2): every line is printed at once; the free VRAM is printed where the driver
reports it (`GL_NVX_gpu_memory_info`) before the cube, after the cube and maps, and per view; a row that raises a GL
error is reported with the free VRAM and dropped, the other rows continue; only the shadow maps the chosen rows read are
created; `--p3-rows` and `--p3-no-depth` run a part.

## (p3a) The depth pass alone [M-RPC]

GPU p50 ms (min – max), 30 rounds after 5. The pass does not depend on the window size, so the two processes are two
repeats.

| Surface | Map | Casters | 1024×768 process | 1920×1080 process |
|---|---:|---|---:|---:|
| cage | 512² | skin | 0.83 (0.59–2.14) | 0.77 (0.34–33.39) |
| cage | 512² | skin + eyes | 1.01 | 0.99 |
| cage | 1024² | skin | 0.85 | 0.72 |
| cage | 1024² | skin + eyes | 1.13 (max 313.91) | 1.00 |
| cage | 2048² | skin | 0.99 | 0.82 |
| cage | 2048² | skin + eyes | 1.11 | 1.11 |
| SubD 1 | 512² | skin | 0.75 | 0.82 |
| SubD 1 | 512² | skin + eyes | 1.05 | 0.90 |
| SubD 1 | 1024² | skin | 0.87 | 0.72 |
| SubD 1 | 1024² | skin + eyes | 1.07 | 1.12 |
| SubD 1 | 2048² | skin | 1.02 | 0.94 |
| SubD 1 | 2048² | skin + eyes | 1.22 | 1.16 |

What it shows:
- **The depth pass is about 1 ms** at every size, with or without the eyes, cage and SubD 1: far under S1's 3 ms target
  (AD-039 §2.5). A pose or morph drag that re-renders the map every frame pays about 1 ms.
- Size hardly matters (0.7–1.2 ms from 512² to 2048²), so the map size is a question of look and memory, not of the
  pass's time.
- LD-0's 9–11.5 ms for its `ld shadow` stand-in (AD-038 §16.1) were therefore **not** the depth pass; they were the
  16-fetch lookup over the frame or something else in that row. Run 2's lookup rows decide (AD-039 C6).
- Single maxima of 33 and 314 ms: one-off stalls (a driver paging or compiling) [H]; the p50 is unaffected.


## Run 2 (commit `01c83dc`, working tree "MODIFIED" = Manu's local files) [M-RPC]

VRAM free (`GL_NVX_gpu_memory_info`): 296 of 512 MiB at the start, 289 after the cube and both maps, 242 during the
frame rows. **Every row ran except `cube env`, `cube dual env` and `p3 all`**: each failed in round 0 with
`GL_OUT_OF_MEMORY` at the skin draw while 270 MiB were free. This is not memory. The stand-in UV binding
(`bind_triangle_uvs` → `GLRenderStore._flush_face_data`) binds the store's face corners as a buffer texture on unit 5,
and the probe had put the cube on unit 5 too [H: two targets on one unit; the other rows have no second target on a
used unit]. The probe's cube is now on unit 8 (AD-039 §2.4); run 3 checks it.

Depth pass alone, GPU p50 ms (1024×768 process): 0.47–0.73 (cage), 0.49–0.90 (SubD 1) from 512² to 2048², with or
without the eyes; the 1920×1080 process gives the same (0.43–1.01).

Cube prefilter, 128², 64 samples: 12.14 ms with the corner fix, 12.11 ms without; corner spread 0.000 at every level
with the fix (as in the container).

Frame rows, GPU p50 ms (`vs ld` = minus `ld frame`), 1024×768:

| Row | cage framed | cage close | SubD 1 framed | SubD 1 close |
|---|---:|---:|---:|---:|
| `ld frame` | 1.68 | 4.58 | 2.23 | 5.26 |
| `shadow 1k x4` | +0.76 | +0.92 | +1.04 | +1.76 |
| `shadow 1k x9` | +1.11 | +1.32 | +1.78 | +2.76 |
| `shadow 1k x16` | +1.17 | +1.51 | +1.94 | +3.08 |
| `shadow 2k x9` | +1.09 | +1.34 | +1.81 | +2.78 |
| `shadow 2k x16` | +1.22 | +1.57 | +1.95 | +3.16 |
| `drag 1k x9` | +7.35 | +8.22 | +9.86 | +10.75 |
| `thick 1k x9` | +0.50 | +0.79 | +0.85 | +1.35 |
| `dual direct` | +0.21 | +0.14 | +0.06 | +0.16 |
| `dual env` | +0.91 | +1.79 | +1.35 | +2.52 |

1920×1080: `ld frame` 3.00 / 7.95 / 3.63 / 8.83; `shadow 1k x9` +1.22 / +1.95 / +2.56 / +3.57; `drag 1k x9` +8.54 /
+8.42 / +8.72 / +9.75; `thick 1k x9` +0.65 / +1.27 / +1.26 / +1.92; `dual direct` +0.09 / +0.26 / +0.10 / +0.29;
`dual env` +1.18 / +3.13 / +2.01 / +4.00. CPU wall of `drag 1k x9`: 24–33 ms.

The shadow darkens 4,929 / 52,518 px (cage framed / close) and 3,805 / 39,046 px (SubD 1), as in the container.

What it decides is in AD-039 §11.1 (S1: 1024², 3 × 3; the drag cost open; S3: the second lobe on the lights only).

## Run 3 (commit `4391e64`, cube rows only) [M-RPC]

With the cube on unit 8, `cube env`, `cube dual env` and `p3 all` **still fail** in round 0 of every view at both sizes
with `GL_OUT_OF_MEMORY`, with 277–311 MiB VRAM free; `ld frame` in the same run draws (1.86 / 2.42 ms framed, cage /
SubD 1). **The unit clash of run 2 was not the cause** (that hypothesis is withdrawn). The prefilter itself works on
this card (12.1 ms, corner spread 0 with the fix), so the failure is in *sampling* the cube in the skin stand-in.

Changed for run 4 (commit after `4391e64`):
- the stand-in's environment lookup is a plain function (`env_at`) instead of a function-like `#define` macro (the
  only construct the cube variants have that no working variant has);
- `--p3-cube-check`: one frame per case, each changing one thing against the failing row - the cube only bound (no
  lookup), seamless filtering off / on, `texture()` instead of `textureLod`, the rendered cube at level 0 only, a cube
  uploaded from the CPU (RGBA16F with and without mips, RGBA8), without the albedo map, without the eyes. Each case
  reports `ok` or its GL error with the free VRAM.

## Run 4 (commit `c05434f`, `--p3-cube-check`, 1024×768, cage framed) [M-RPC]

316 MiB VRAM free at the start, 292–314 MiB at each failure.

| Case | Cube | Result |
|---|---|---|
| A bound only, seamless off / B on | rendered | ok / ok |
| C cube env, seamless off | rendered | **ok** (first lookup of this cube) |
| D cube env, seamless on | rendered | FAILED |
| E `texture()`, seamless off | rendered | FAILED |
| F level 0 only | a second rendered cube | **ok** (its first lookup) |
| G / H uploaded RGBA16F, mips / level 0 | uploaded | ok / ok |
| I uploaded RGBA8, mips | uploaded | ok |
| J no albedo map | rendered (the first one) | FAILED |
| K no eyes | rendered (the first one) | FAILED (same program as C) |

Reading: neither the seamless flag, nor `textureLod`, nor the program, the albedo map or the eyes decide it.
**A cube rendered through an FBO samples once and then fails every later draw; a cube uploaded from the CPU always
works.** That fits every run: runs 2–3 built the rendered cube, read it back (`corner_spread`), and their first cube
draw already failed [H: a driver defect of this old card with FBO-rendered float cube textures]. The macro change of
run 3 → 4 did not matter (C passes, K fails with the same program).

Changed for run 5:
- `cube_via_cpu`: the rendered chain read back and uploaded into a fresh cube (container: about 2 ms wall for 128²,
  1.3 MiB); the frame rows now sample that copy;
- the check adds L (a fresh rendered cube, 5 frames: expected to fail after the first) and M (rendered + CPU copy,
  5 frames: expected to work).

## Run 5 (commit `694def7`) [M-RPC]

**5a, `--p3-cube-check`:** A–K as in run 4. **L** (a freshly rendered cube, 5 frames) failed in its first frame;
**M** (rendered, then read back and uploaded) drew all 5 frames (63.2 / 1.6 / 1.4 / 1.4 / 1.4 ms GPU, the first with
the compile). The CPU copy of the 128² chain took 24.1 ms wall. Reading: an FBO-rendered float cube cannot be sampled
reliably on this card and driver (it sometimes passes its first lookup, C and F, sometimes not, L); a CPU-uploaded
copy always works [H: a driver defect].

**5b, the cube rows on the copy** (copy 16.9 / 17.4 ms wall once, prefilter 12.1 ms GPU). GPU p50 ms, `vs ld` =
minus `ld frame`:

| Row | 1024 cage framed | 1024 cage close | 1024 SubD 1 framed | 1024 SubD 1 close | 1920 SubD 1 close |
|---|---:|---:|---:|---:|---:|
| `ld frame` | 1.98 | 4.58 | 2.21 | 5.25 | 8.82 |
| `cube env` | −0.41 | −1.25 | −0.62 | −1.48 | −2.60 |
| `cube dual env` | −0.67 | −1.06 | −0.54 | −1.28 | −2.22 |
| `p3 all` | −0.29 | −0.40 | +0.08 | −0.21 | −0.69 |

`p3 all` = shadow 1k × 9 + thickness + dual lobe on the lights + the cube's environment: **1.69 / 2.29 ms GPU framed
at 1024×768 (5 / 7 % of 33.3 ms), about what `ld frame` costs without any P3 effect.** The cube lookup is cheaper
than the analytic studio by more than the shadow, thickness and dual lobe cost together.

## Next

P3-0 is complete. The production slices measure themselves through `probe_lookdev_room.py` (AD-039 §11.2).
