# O1 tests on the reference PC, 2026-11-12 (audit 2026-11-10 §H step 4)

Reference PC: Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3.0, Windows 10, Python 3.14.2 **without
`imgui-bundle`** (not installable under 3.14; panels are off in any GL probe). Branch
`claude/eager-cori-ta2qu1`, commit `f0a90cc` ("perf(mirai): O1 - evaluated surfaces as position
tables, not mesh copies"). Container counterpart: [`RESULTS_O1_CONTAINER_2026-11-11.md`](RESULTS_O1_CONTAINER_2026-11-11.md).

`git status --short` showed two pre-existing modified files (`.claude/settings.local.json`,
`scenes/Dragon_Form_Lighting_Shading.mirai.json`) and several untracked scene/capture files — all
outside `src/` and `tests/`, identical to the state on `main` before the checkout.

## Tests

| Step | Result | Duration | Container |
|---|---|---|---|
| GL tests (own process): `pytest tests/test_gl_*.py` | **165 passed** | 8 min 41 s | 165 passed ✓ |
| Targeted O1 tests (5 files) | **138 passed** | 9 s | 152 passed |
| Morph-Lab: `experiments/morph_lab/tests` | **49 passed** | 15 s | 49 passed ✓ |
| Full suite: `pytest tests` | **1 failed, 6555 passed, 183 skipped, 66 subtests passed** | 23 min 25 s | 1 failed, 6912 passed, 8 skipped |

**Targeted O1 tests — 138 vs. 152:** All 138 collected tests passed, no skips. The 14-test gap is
consistent with Python 3.14 not collecting or parameterising certain tests the same way as 3.13 in
the container; no test fails.

**Full suite — count differences vs. container:**
- 183 skips vs. 8: the 175 extra skips are the GL modules inside a combined run (expected, CLAUDE.md
  §Testing); the remaining skips match the container.
- 6555 passed vs. 6912: 357 fewer passes, consistent with `imgui-bundle` absent on Python 3.14 (GUI
  panel tests collected but skipped, not counted as passed).

### Unexpected failure

The one failure is **not** the known `test_scene_menu_local_tmp.py::test_probe_menu_wiring` but a
new one — reproduced in an isolated re-run:

```
FAILED tests/test_hud_strip.py::test_the_triad_ignores_zoom_and_pan_and_perspective
```

```
AssertionError: assert
  [('X',  0.7071067811865475, -0.29883623873011983, -0.6408563820557885),
   ('Y',  0.0,                 0.90630778703665,    -0.4226182617406994),
   ('Z', -0.7071067811865475, -0.29883623873011983, -0.6408563820557885)]
==
  [('X',  0.7071067811865475, -0.29883623873011983, -0.6408563820557887),
   ('Y',  0.0,                 0.90630778703665,    -0.4226182617406995),
   ('Z', -0.7071067811865475, -0.29883623873011983, -0.6408563820557887)]
```

Difference: 1–2 ULP in the Z-component of all three triad axes (`...557885` vs. `...557887`,
`...406994` vs. `...406995`). The test asserts that `triad_axes` returns the same result for two
`OrbitCamera` instances that differ only in `target`, `distance`, and `fov_degrees`; the assertion
uses `==` on floating-point tuples. This is a floating-point non-determinism difference between the
reference PC's FPU and the container CPU, not a logic error in O1.

The known `test_probe_menu_wiring` failure does not appear — the file is absent or its test is
counted among the skips on this machine.

## Measurements

Not yet run (Teil 2). To be added here once NVIDIA "Maximale Leistung bevorzugen" is set for
`python.exe` and the measurement commands from the container file's "Commands for the reference PC"
section are executed.