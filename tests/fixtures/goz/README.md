# GoZ fixtures (ZBrush 2022.0.8, reference PC, 2026-11-05)

Byte copies of files ZBrush wrote in the E1 run (`experiments/goz_probe/README.md` §10a); copied here so the
Production tests do not depend on the experiment folder (AGENTS.md §8a: nothing in `tests/` reads `experiments/`).
The `zb2022_P1_*` files came through P1 and are already in the bridge frame. E1 sent the other meshes in Mirai's raw frame; the tests flip them to the bridge's `(x, −y, −z)` (exact in float32), which is
what ZBrush returns for a flipped send (E1 T5.2: ZBrush's GoZ round trip is the identity).

| File | Source capture | Content |
|---|---|---|
| `zb2022_C_unchanged.GoZ` | `20261105-174708_218_receive` | head (`examples/meshes/head_basemesh.obj`, 326 v / 324 quads) sent and returned unchanged |
| `zb2022_C_move_brush.GoZ` | `20261105-173432_632_receive` | head after Move-brush strokes: 101 points moved, 225 bit-identical |
| `zb2022_B_move_brush.GoZ` | `20261105-181041_145_receive` | E1 mesh B (Mirai sphere minus 4 faces: 481 v / 508 f, 64 triangles, open border): 12 moved |
| `zb2022_C_divided_once.GoZ` | `20261105-181407_335_receive` | head divided once (SMT on): base topology, every point = its one-step Catmull-Clark vertex point |
| `zb2022_C_divided_no_smt.GoZ` | `20261105-185718_469_receive` | T7b: head divided once with SMT off: bit-identical |
| `zb2022_C_cage.GoZ` | `20261105-185830_405_receive` | T7c: divided with SMT on, lowest level, Cage: every point moved by ≤ 4.1e-4 |
| `zb2022_P1_head_move_symx.GoZ` | `ticket_01793909441692885900_16724` (P1, bridge frame) | head sent by P1, Move brush with ZBrush X symmetry: all 145 mirror pairs bit-exact |
| `zb2022_P1_head_smooth_symx.GoZ` | `ticket_01793909578397887700_19924` (P1, bridge frame) | then Smooth brush with X symmetry: 76 of 145 pairs off by up to 0.0102, 13 of 36 seam points off the plane |
| `zb2022_A_obj_import.GoZ` | E1 T2 (`experiments/goz_probe/tests/fixtures`) | ZBrush's own file of an OBJ-imported tripod: MRGB / MASK16 / GROUPS / CREASE blocks |
| `zb2022_E2_head_groups_unchanged.GoZ` | `20261105-223403_371_receive` (E2, bridge frame) | head sent with a GROUPS block (four bands by height, ids 101–104) and returned unchanged: ZBrush keeps every face's id |
| `zb2022_E2_head_groups_regrouped.GoZ` | `20261105-223614_741_receive` (E2, bridge frame) | then 12 faces of band 104 regrouped in ZBrush (mask, Ctrl+W): they come back as a new id 3225, every other face keeps its id; points bit-identical |

The E2 files carry the probe's ids 101–104; the bridge sends region `k` as id `k`, so the tests map 101–104 to 1–4
(ZBrush returns whatever ids it was sent, E2) and keep 3225 as ZBrush's new group.
| `zb2022_E3_head_uvs_as_sent.GoZ` | `20261106-095115_060_receive` (E3, bridge frame) | head sent with its UVs (UV4 block, OBJ `vt` values) and returned unchanged: UVs identical (≤ 3e-8), no flip |
| `zb2022_E3_head_uvmaster.GoZ` | `20261106-095441_815_receive` (E3) | then *UV Master → Unwrap*: new UVs on all 324 faces, points bit-identical |
| `zb2022_E3_head_uvmaster_texture.GoZ` | `20261106-095617_452_receive` (E3) | then polypaint, *New From Polypaint*: same UVs, plus a TEXTURE_MAP_PATH block naming `…/E1_C_P1_UV1_TXTR.tif` (2048², uncompressed RGB, stored bottom-up; the 12 MB image itself is not copied here) |
| `zb2022_E3_head_bump_target.GoZ` | `20261106-095824_807_receive` (E3) | the head plus the probe's bump target (`make_meshes.bump_offsets`), sent as its own object beside the base and returned unchanged: bit-identical to `b + d` |
