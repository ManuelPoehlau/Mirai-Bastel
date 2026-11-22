# LookDev P3-0 probe — reference PC, runs 1 and 2 (Manu, 2026-11-22)

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

## Next

Run 3, only the cube rows:

```
python experiments\drag_cost\probe_lookdev.py --p3 --p3-no-depth --p3-rows "cube env,cube dual env,p3 all" | Tee-Object -FilePath lookdev_p3_0_run3.txt
```
