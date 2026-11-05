# GoZ fixtures (ZBrush 2022.0.8, reference PC, 2026-11-05)

Byte copies of files ZBrush wrote in the E1 run (`experiments/goz_probe/README.md` §10a); copied here so the
Production tests do not depend on the experiment folder (AGENTS.md §8a: nothing in `tests/` reads `experiments/`).
E1 sent the meshes in Mirai's raw frame; the tests flip them to the bridge's `(x, −y, −z)` (exact in float32), which is
what ZBrush returns for a flipped send (E1 T5.2: ZBrush's GoZ round trip is the identity).

| File | Source capture | Content |
|---|---|---|
| `zb2022_C_unchanged.GoZ` | `20261105-174708_218_receive` | head (`examples/meshes/head_basemesh.obj`, 326 v / 324 quads) sent and returned unchanged |
| `zb2022_C_move_brush.GoZ` | `20261105-173432_632_receive` | head after Move-brush strokes: 101 points moved, 225 bit-identical |
| `zb2022_B_move_brush.GoZ` | `20261105-181041_145_receive` | E1 mesh B (Mirai sphere minus 4 faces: 481 v / 508 f, 64 triangles, open border): 12 moved |
| `zb2022_C_divided_once.GoZ` | `20261105-181407_335_receive` | head divided once (SMT on): base topology, every point = its one-step Catmull-Clark vertex point |
| `zb2022_C_divided_no_smt.GoZ` | `20261105-185718_469_receive` | T7b: head divided once with SMT off: bit-identical |
| `zb2022_C_cage.GoZ` | `20261105-185830_405_receive` | T7c: divided with SMT on, lowest level, Cage: every point moved by ≤ 4.1e-4 |
| `zb2022_A_obj_import.GoZ` | E1 T2 (`experiments/goz_probe/tests/fixtures`) | ZBrush's own file of an OBJ-imported tripod: MRGB / MASK16 / GROUPS / CREASE blocks |
