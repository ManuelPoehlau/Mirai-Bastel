# LookDev LD-0 probe — reference PC run (AD-038, <DATE>) — TEMPLATE

> Copy this file to `RESULTS_LOOKDEV_REFERENCE_PC_<YYYY-MM-DD>.md`, paste the console output under "Output", and fill
> the tables from it (the agent can do the filling from the pasted output). Delete this note.

Machine: the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX+, GL 3.3.0, Windows 10, Python 3.12 in `.venv312`) —
**MEASURED [RPC]**. Run by Manu on <DATE>.

Before the run: NVIDIA control panel → "Energieverwaltungsmodus: Maximale Leistung bevorzugen" (as for
`probe_shading_gpu.py`). Close other GPU-heavy programs.

Command (PowerShell, repository root, `.venv312` active):

```
python experiments\drag_cost\probe_lookdev.py | Tee-Object -FilePath lookdev_ld0.txt
```

(1024×768 with every extra, then 1920×1080 with the frame rows, each in its own process. If a part fails, rerun
without it: `--skip cube`, `--skip depth`, `--skip uv`, `--skip compile`; a single size: `--size 1024 768`.)

Source line printed by the probe (commit, working tree): `<…>`
Driver "maximum performance" set: <yes / no>

## (a) Frame rows, GPU p50 ms (GL_TIME_ELAPSED)

| Surface / view / size | coverage | worklight | wl eyes full | ld skin | ld frame | ld no env | ld no map | ld shadow | app render |
|---|---|---|---|---|---|---|---|---|---|
| cage / framed / 1024×768 | | | | | | | | | |
| cage / close / 1024×768 | | | | | | | | | |
| subd1 / framed / 1024×768 | | | | | | | | | |
| subd1 / close / 1024×768 | | | | | | | | | |
| cage / framed / 1920×1080 | | | | | | | | — | |
| cage / close / 1920×1080 | | | | | | | | — | |
| subd1 / framed / 1920×1080 | | | | | | | | — | |
| subd1 / close / 1920×1080 | | | | | | | | — | |

CPU p50 (draw + glFinish) of `worklight` / `ld frame`, 1024×768 framed: cage <…> / <…>, SubD 1 <…> / <…>.

**LD-D10 lines** (printed): `<paste the two "LD-D10 [...]" lines>`

## (b) UV request, ms wall

| Surface | triangles | request on: first / p50 | first draw after: first / p50 | request off: first / p50 | `_triangle_uvs_flat` p50 |
|---|---|---|---|---|---|
| cage | | | | | |
| subd1 | | | | | |

## (c) RGBA16F cube (P3)

- FBO status: <complete for every face and level / …>; glGetError <…>
- chain, 64 samples: <…> ms GPU; 256 samples: <…> ms GPU
- level 0 vs `td_env`, worst relative error: <…>; `textureLod` read-back, worst relative error: <…>

## (d) Depth texture (P3)

- depth FBO: <complete / INCOMPLETE 0x…>; texels written: <…> of 4194304
- shadow lookup darkens: framed <…> px, close <…> px (cage); framed <…>, close <…> (SubD 1)

## (compile) first use, wall ms

| Eye variant | cold | as shipped | again |
|---|---|---|---|
| plain | | | |
| look | | | |
| look+iris | | | |
| look+iris+sclera | | | |

`EyePass.program()` fresh: <…> ms. Skin stand-in variants (cold): <…>.

## Reading (to be written after the run; no verdict in the template)

- LD-D10 (≥ 30 fps, framed, 1024×768): `ld frame` = <…> % of 33.3 ms → full skin in M1 / start with `ENV_SPEC` 0.
- Modelling Room baseline for E16: `worklight` / `app render` rows above.
- UV request on room entry: <acceptable without a status line / needs one>.
- Cold compile: <no visible stall / pre-compile on entry (AD-038 §15 Q4)>.
- P3 notes: cube render-to-face <works / fails>, depth texture <works / fails>.

## Output

```
<paste lookdev_ld0.txt here>
```
