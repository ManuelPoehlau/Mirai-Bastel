# LookDev P3-0 probe — reference PC, run 1 (Manu, 2026-11-22): aborted, partial

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

## Next

Run 2 with the changed probe, same command:

```
python experiments\drag_cost\probe_lookdev.py --p3 | Tee-Object -FilePath lookdev_p3_0_run2.txt
```

If a row fails again, its line names the row and the free VRAM; the rest of the table still comes.
