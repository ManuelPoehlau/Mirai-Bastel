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

## Skip list

Collect-only (`pytest tests --collect-only -q -rs`):

```
tests/test_application_knife_cross_face.py::test_the_status_names_hidden_crossings_and_skipped_stretches
tests/test_application_material.py::test_references_are_skipped_and_stay_blue
tests/test_application_seam_to_plane.py::test_paired_vertices_are_skipped_or_refused
tests/test_can_run.py::test_hidden_stage_is_skipped_without_operands
tests/test_core_delete_dissolve.py::test_delete_faces_noop_and_error
tests/test_core_delete_dissolve.py::test_delete_edges_noop_and_error
tests/test_core_delete_dissolve.py::test_delete_vertices_grid_corner_and_noop_and_error
tests/test_core_delete_dissolve.py::test_dissolve_edges_noop_and_errors
tests/test_core_delete_dissolve.py::test_dissolve_faces_errors
tests/test_core_delete_dissolve.py::test_dissolve_vertex_errors
tests/test_input_binding.py::KeymapValidationTests::test_invalid_json_syntax_raises_controlled_error
tests/test_input_binding.py::KeymapDuplicateTests::test_same_key_in_different_contexts_is_not_an_error
tests/test_knife_cross_face.py::test_hole_visible_pieces_cut_gap_skipped_hud_note
tests/test_knife_cross_face.py::test_without_occlusion_nothing_is_hidden_and_nothing_skipped
tests/test_object_outliner.py::test_paste_without_copy_or_outside_mode_4_is_refused_and_a_deleted_source_is_skipped
tests/test_soft_selection_influence.py::test_stale_ids_are_skipped
tests/test_soft_selection_ops.py::test_stale_ids_in_influence_skipped[SoftMoveOperation]
tests/test_soft_selection_ops.py::test_stale_ids_in_influence_skipped[SoftRotateOperation]
tests/test_soft_selection_ops.py::test_stale_ids_in_influence_skipped[SoftScaleOperation]
tests/test_subdivision_unsupported.py::test_a8_is_a_value_error_not_a_crash_on_valid_input
tests/test_tool_integration.py::SelectionResolutionIntegrationTests::test_stale_selection_handles_are_skipped
tests/test_topology_transaction_seam.py::test_vertex_connect_nothing_connectable_signal_and_errors
tests/test_view_state.py::test_broken_section_is_skipped_not_fatal
tests/test_wp03c_tangent_basis.py::TangentBasisTests::test_multi_face_selection_raises_error
tests/test_wp03c_tangent_basis.py::TangentBasisTests::test_vertex_mode_selection_raises_error
tests/test_wp03d_normal_plane_constraints.py::NormalPlaneRegressionTests::test_multi_face_plane_raises_error
SKIPPED [1] tests\test_gui_imgui_window.py:12: could not import 'imgui_bundle': No module named 'imgui_bundle'
SKIPPED [1] tests\test_gui_menus.py:226: could not import 'imgui_bundle': No module named 'imgui_bundle'
SKIPPED [1] tests\test_main_wiring.py:44: pyglet.window unavailable: Library "EGL" not found.
SKIPPED [1] tests\test_pyglet_input.py:0: pyglet/Display fehlt - pip install -r requirements-dev.txt; headless: xvfb-run -a pytest
SKIPPED [1] tests\test_scene_menu_local_tmp.py:22: pyglet.window unavailable: Library "EGL" not found.
SKIPPED [1] tests\test_soft_selection_input.py:34: pyglet.window unavailable: Library "EGL" not found.
SKIPPED [1] tests\test_transform_alt_orbit.py:0: pyglet/Display fehlt - pip install -r requirements-dev.txt; headless: xvfb-run -a 
pytest
6732 tests collected in 6.45s
```

Full run (`pytest tests -q -rs`), SKIPPED/FAILED/passed/failed lines only:

```
SKIPPED [1] tests\test_gui_imgui_window.py:12: could not import 'imgui_bundle': No module named 'imgui_bundle'
SKIPPED [1] tests\test_gui_menus.py:226: could not import 'imgui_bundle': No module named 'imgui_bundle'
SKIPPED [1] tests\test_main_wiring.py:44: pyglet.window unavailable: Library "EGL" not found.
SKIPPED [1] tests\test_pyglet_input.py:0: pyglet/Display fehlt - pip install -r requirements-dev.txt; headless: xvfb-run -a pytest
SKIPPED [1] tests\test_scene_menu_local_tmp.py:22: pyglet.window unavailable: Library "EGL" not found.
SKIPPED [1] tests\test_soft_selection_input.py:34: pyglet.window unavailable: Library "EGL" not found.
SKIPPED [1] tests\test_transform_alt_orbit.py:0: pyglet/Display fehlt - pip install -r requirements-dev.txt; headless: xvfb-run -a 
pytest
SKIPPED [2] tests\test_application_symmetric_tools.py:927: vertex Dissolve has no no-cleanup variant
SKIPPED [1] tests\test_application_symmetry_cycle.py:455: pyglet.window unavailable: Library "EGL" not found.
SKIPPED [1] tests\test_gl_attach.py:57: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_bridge.py:56: no GL context available: Library "EGL" not found.
SKIPPED [4] tests\test_gl_component_overlays.py:141: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_component_overlays.py:158: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_component_overlays.py:173: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_component_overlays.py:186: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_component_overlays.py:207: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_component_overlays.py:229: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_detach.py:58: no GL context available: Library "EGL" not found.
SKIPPED [4] tests\test_gl_face_data_layout.py:169: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_face_data_layout.py:176: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_face_data_layout.py:182: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_face_data_layout.py:195: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_face_data_layout.py:205: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_face_data_layout.py:220: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_face_data_layout.py:242: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_face_data_layout.py:250: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_face_data_layout.py:275: no GL context available: Library "EGL" not found.
SKIPPED [3] tests\test_gl_gizmo_overlay.py:64: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_gpu_picking.py:92: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_gpu_picking.py:96: no GL context available: Library "EGL" not found.
SKIPPED [4] tests\test_gl_gpu_picking.py:113: no GL context available: Library "EGL" not found.
SKIPPED [4] tests\test_gl_gpu_picking.py:132: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_gpu_picking.py:151: no GL context available: Library "EGL" not found.
SKIPPED [6] tests\test_gl_gpu_picking.py:175: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_gpu_picking.py:188: no GL context available: Library "EGL" not found.
SKIPPED [3] tests\test_gl_gpu_picking.py:224: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_gpu_picking.py:247: no GL context available: Library "EGL" not found.
SKIPPED [4] tests\test_gl_gpu_picking.py:271: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_gpu_picking.py:288: no GL context available: Library "EGL" not found.
SKIPPED [4] tests\test_gl_gpu_picking.py:303: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_hud_marks.py:87: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_hud_marks.py:110: no GL context available: Library "EGL" not found.
SKIPPED [4] tests\test_gl_hud_marks.py:131: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_hud_marks.py:152: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_knife_overlay.py:109: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_knife_overlay.py:153: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_line_overlay.py:149: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_line_overlay.py:156: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_line_overlay.py:166: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_line_overlay.py:185: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_line_overlay.py:212: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_line_overlay.py:239: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_line_overlay.py:280: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_morph_picking.py:123: no GL context available: Library "EGL" not found.
SKIPPED [4] tests\test_gl_morph_picking.py:130: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_morph_picking.py:148: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_morph_picking.py:162: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_morph_picking.py:176: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_morph_picking.py:190: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_morph_picking.py:197: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_point_overlay.py:109: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_point_overlay.py:139: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_point_overlay.py:166: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_point_overlay.py:176: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_region_tint.py:74: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_region_tint.py:92: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_region_tint.py:123: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_mesh_incremental.py:99: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store.py:55: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store.py:78: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store.py:96: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store.py:116: no GL context available: Library "EGL" not found.
SKIPPED [4] tests\test_gl_render_store.py:165: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store.py:246: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store.py:272: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store_patch.py:103: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store_patch.py:116: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store_patch.py:132: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_render_store_patch.py:159: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_shading.py:127: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_shading.py:138: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:158: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_shading.py:165: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:178: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:195: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:208: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:220: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:237: no GL context available: Library "EGL" not found.
SKIPPED [3] tests\test_gl_shading.py:263: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:277: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:299: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:311: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_shading.py:318: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_soft_bands.py:94: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_soft_bands.py:114: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_soft_bands.py:125: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_soft_bands.py:145: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_soft_shading.py:48: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_soft_shading.py:71: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_subdivision_lines.py:123: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_subdivision_lines.py:137: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_subdivision_lines.py:148: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_subdivision_lines.py:160: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_subdivision_lines.py:181: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_subdivision_lines.py:198: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_subdivision_lines.py:208: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_gl_subdivision_lines.py:228: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_texture.py:114: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_texture.py:124: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_texture.py:141: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_texture.py:159: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_texture.py:169: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_weld.py:57: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_gl_weld.py:103: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_main_entry_point.py:50: no GL context available: Library "EGL" not found.
SKIPPED [1] tests\test_main_entry_point.py:69: no GL context available: Library "EGL" not found.
SKIPPED [2] tests\test_symmetric_removal.py:150: Vertex Dissolve has no variant (the command does nothing there)
SKIPPED [1] tests\test_symmetric_removal.py:209: no variant
SKIPPED [1] tests\test_symmetric_removal.py:615: no variant
SKIPPED [2] tests\test_symmetric_removal.py:641: no variant
1 failed, 6555 passed, 183 skipped, 66 subtests passed in 1398.80s (0:23:18)
```

## Measurements, 2026-11-12

NVIDIA "Maximale Leistung bevorzugen" set for `python.exe` (confirmed by Manu before the run).

### After O1 (main, commit 1871107)

`python experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj`:

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 1871107556, working tree MODIFIED, src/ tree 559d88b8e2
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                3583 ms   process     170 MiB (   +117)
  save scene file                                                559 ms   process     172 MiB (     +2)
    file size 11.7 MiB
  parse scene file (scene_from_json, no viewport)               1019 ms   process     185 MiB (    +13)
  write one target, offsets on 15 % of the points                412 ms   process     174 MiB (    -11)
  first weight step 0 -> 60 % (builds the mix surface)          1453 ms   process     225 MiB (    +52)
    of it: stage evaluation 103 ms (MixSurface / SkinSurface.update), new RenderMesh 1330 ms
  next weight step (patch) + frame                                68 ms   process     227 MiB (     +2)
    of it: stage evaluation 7 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             98 ms   process     228 MiB (     +1)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     1615 ms   process     253 MiB (    +25)
    of it: stage evaluation 31 ms (MixSurface / SkinSurface.update), new RenderMesh 1370 ms
  next pose step (patch, morph + skin) + frame                    72 ms   process     254 MiB (     +1)
    of it: stage evaluation 14 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

`python experiments\drag_cost\probe_scale_audit.py --only chain --assets dense`:

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 1871107556, working tree MODIFIED, src/ tree 559d88b8e2
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                               12584 ms   process     457 MiB (   +405)
  save scene file                                               2044 ms   process     460 MiB (     +3)
    file size 46.7 MiB
  parse scene file (scene_from_json, no viewport)               4167 ms   process     505 MiB (    +45)
  write one target, offsets on 15 % of the points               1807 ms   process     460 MiB (    -46)
  first weight step 0 -> 60 % (builds the mix surface)          6149 ms   process     674 MiB (   +215)
    of it: stage evaluation 378 ms (MixSurface / SkinSurface.update), new RenderMesh 5729 ms
  next weight step (patch) + frame                               273 ms   process     676 MiB (     +2)
    of it: stage evaluation 32 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            413 ms   process     686 MiB (    +10)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     6672 ms   process     730 MiB (    +44)
    of it: stage evaluation 136 ms (MixSurface / SkinSurface.update), new RenderMesh 5770 ms
  next pose step (patch, morph + skin) + frame                   294 ms   process     730 MiB (     +0)
    of it: stage evaluation 61 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

`python experiments\drag_cost\probe_d3_acceptance.py`:

```
Panels aus: imgui-bundle fehlt (pip install -r requirements-dev.txt)
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 1871107556, working tree MODIFIED, src/ tree 559d88b8e2
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels off; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   307.45  p95   317.85  max   355.04 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.23  p95     0.29
    tick (update_viewport)                   p50   288.59  p95   299.38
    on_draw + glFinish                       p50    18.74  p95    22.01
      tick: stage evaluation (mix + skin)    p50    57.75  p95    60.28
      tick: RenderMesh._sync_geometry        p50   221.59  p95   228.05
        of it: face data -> store            p50    22.45  p95    24.49
      draw: viewport render (faces, wire, overlays) p50     3.83  p95     4.50
        of it: face-data upload              p50     0.88  p95     1.28
      draw: gizmo / bones                    p50     0.93  p95     1.45
      draw: HUD                              p50     0.97  p95     1.33
      draw: triad                            p50     0.28  p95     0.54
      draw: rest (clear, sync, GPU wait)     p50    12.27  p95    14.94
      gpu: vertex-buffer upload              p50     4.16  p95     6.18
      gpu: mesh draw (face data + shaded pass) p50    11.47  p95    15.63
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   375.16  p95   389.26  max   471.73 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.11  p95     0.13
    tick (update_viewport)                   p50   326.04  p95   338.65
    on_draw + glFinish                       p50    48.41  p95    56.96
      tick: stage evaluation (mix + skin)    p50    89.85  p95    96.05
      tick: RenderMesh._sync_geometry        p50   220.48  p95   228.89
        of it: face data -> store            p50    22.89  p95    25.81
      draw: viewport render (faces, wire, overlays) p50     3.81  p95     4.76
        of it: face-data upload              p50     0.84  p95     1.33
      draw: gizmo / bones                    p50     6.78  p95     7.62
      draw: HUD                              p50    24.57  p95    29.02
      draw: triad                            p50     0.31  p95     0.65
      draw: rest (clear, sync, GPU wait)     p50    12.67  p95    15.63
      gpu: vertex-buffer upload              p50    33.40  p95    42.84
      gpu: mesh draw (face data + shaded pass) p50    11.48  p95    45.60
    NOTE gpu mesh draw varies 11.33-49.15 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   313.35  p95   333.55  max   371.06 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.24  p95     0.29
    tick (update_viewport)                   p50   293.66  p95   312.91
    on_draw + glFinish                       p50    19.51  p95    21.74
      tick: stage evaluation (mix + skin)    p50    59.26  p95    62.62
      tick: RenderMesh._sync_geometry        p50   225.87  p95   240.95
        of it: face data -> store            p50    23.12  p95    25.51
      draw: viewport render (faces, wire, overlays) p50     4.09  p95     5.24
        of it: face-data upload              p50     0.73  p95     1.24
      draw: gizmo / bones                    p50     0.85  p95     1.30
      draw: HUD                              p50     0.92  p95     1.49
      draw: triad                            p50     0.28  p95     0.54
      draw: rest (clear, sync, GPU wait)     p50    12.70  p95    14.58
      gpu: vertex-buffer upload              p50     4.52  p95     6.18
      gpu: mesh draw (face data + shaded pass) p50    11.38  p95    16.34
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   379.47  p95   396.85  max   454.37 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.11  p95     0.14
    tick (update_viewport)                   p50   331.93  p95   344.14
    on_draw + glFinish                       p50    49.08  p95    52.60
      tick: stage evaluation (mix + skin)    p50    91.09  p95   101.20
      tick: RenderMesh._sync_geometry        p50   224.56  p95   232.73
        of it: face data -> store            p50    23.36  p95    26.01
      draw: viewport render (faces, wire, overlays) p50     4.19  p95     5.36
        of it: face-data upload              p50     0.85  p95     1.07
      draw: gizmo / bones                    p50     6.80  p95     7.50
      draw: HUD                              p50    24.37  p95    26.69
      draw: triad                            p50     0.33  p95     0.54
      draw: rest (clear, sync, GPU wait)     p50    12.88  p95    16.04
      gpu: vertex-buffer upload              p50    33.67  p95    37.15
      gpu: mesh draw (face data + shaded pass) p50    11.37  p95    46.15
    NOTE gpu mesh draw varies 11.23-48.74 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### Before O1 (worktree at commit 830f62e)

`python experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj`:

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 830f62e6d3, working tree clean
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                3504 ms   process     172 MiB (   +117)
  save scene file                                                505 ms   process     175 MiB (     +3)
    file size 11.7 MiB
  parse scene file (scene_from_json, no viewport)               1070 ms   process     187 MiB (    +12)
  write one target, offsets on 15 % of the points                425 ms   process     176 MiB (    -11)
  first weight step 0 -> 60 % (builds the mix surface)          2218 ms   process     284 MiB (   +108)
    of it: stage evaluation 852 ms (MixSurface / SkinSurface.update), new RenderMesh 1350 ms
  next weight step (patch) + frame                                69 ms   process     284 MiB (     +1)
    of it: stage evaluation 10 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             99 ms   process     284 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     2403 ms   process     366 MiB (    +82)
    of it: stage evaluation 708 ms (MixSurface / SkinSurface.update), new RenderMesh 1351 ms
  next pose step (patch, morph + skin) + frame                    78 ms   process     368 MiB (     +2)
    of it: stage evaluation 18 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

`python experiments\drag_cost\probe_scale_audit.py --only chain --assets dense`:

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 830f62e6d3, working tree clean
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                               12013 ms   process     456 MiB (   +404)
  save scene file                                               2160 ms   process     459 MiB (     +4)
    file size 46.7 MiB
  parse scene file (scene_from_json, no viewport)               4276 ms   process     505 MiB (    +46)
  write one target, offsets on 15 % of the points               1645 ms   process     459 MiB (    -46)
  first weight step 0 -> 60 % (builds the mix surface)          9452 ms   process     881 MiB (   +421)
    of it: stage evaluation 3367 ms (MixSurface / SkinSurface.update), new RenderMesh 6035 ms
  next weight step (patch) + frame                               286 ms   process     880 MiB (     -1)
    of it: stage evaluation 45 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            411 ms   process     888 MiB (     +8)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     9829 ms   process    1170 MiB (   +283)
    of it: stage evaluation 2852 ms (MixSurface / SkinSurface.update), new RenderMesh 5842 ms
  next pose step (patch, morph + skin) + frame                   302 ms   process    1171 MiB (     +0)
    of it: stage evaluation 72 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

`python experiments\drag_cost\probe_d3_acceptance.py`:

```
Panels aus: imgui-bundle fehlt (pip install -r requirements-dev.txt)
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 830f62e6d3, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels off; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   319.44  p95   334.65  max   359.51 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.24  p95     0.32
    tick (update_viewport)                   p50   300.19  p95   315.75
    on_draw + glFinish                       p50    19.14  p95    22.36
      tick: stage evaluation (mix + skin)    p50    67.95  p95    71.29
      tick: RenderMesh._sync_geometry        p50   222.83  p95   235.53
        of it: face data -> store            p50    22.76  p95    25.74
      draw: viewport render (faces, wire, overlays) p50     3.87  p95     4.98
        of it: face-data upload              p50     0.79  p95     1.15
      draw: gizmo / bones                    p50     0.89  p95     1.38
      draw: HUD                              p50     0.95  p95     1.29
      draw: triad                            p50     0.29  p95     0.57
      draw: rest (clear, sync, GPU wait)     p50    12.73  p95    15.75
      gpu: vertex-buffer upload              p50     4.09  p95     5.88
      gpu: mesh draw (face data + shaded pass) p50    11.45  p95    15.68
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   401.01  p95   436.74  max  1559.20 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.11  p95     0.13
    tick (update_viewport)                   p50   351.43  p95   373.34
    on_draw + glFinish                       p50    49.16  p95    59.25
      tick: stage evaluation (mix + skin)    p50   110.56  p95   117.12
      tick: RenderMesh._sync_geometry        p50   224.03  p95   241.08
        of it: face data -> store            p50    23.21  p95    25.62
      draw: viewport render (faces, wire, overlays) p50     3.76  p95     4.83
        of it: face-data upload              p50     0.76  p95     1.25
      draw: gizmo / bones                    p50     6.90  p95     7.96
      draw: HUD                              p50    25.03  p95    34.00
      draw: triad                            p50     0.31  p95     0.52
      draw: rest (clear, sync, GPU wait)     p50    12.65  p95    14.29
      gpu: vertex-buffer upload              p50    33.66  p95    39.98
      gpu: mesh draw (face data + shaded pass) p50    11.49  p95    46.59
    NOTE gpu mesh draw varies 11.30-1207.53 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   327.69  p95   341.81  max   408.02 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.24  p95     0.29
    tick (update_viewport)                   p50   306.88  p95   322.72
    on_draw + glFinish                       p50    19.19  p95    21.93
      tick: stage evaluation (mix + skin)    p50    68.85  p95    73.56
      tick: RenderMesh._sync_geometry        p50   227.70  p95   239.38
        of it: face data -> store            p50    22.95  p95    25.52
      draw: viewport render (faces, wire, overlays) p50     4.15  p95     5.59
        of it: face-data upload              p50     0.81  p95     1.17
      draw: gizmo / bones                    p50     0.88  p95     1.51
      draw: HUD                              p50     0.92  p95     1.31
      draw: triad                            p50     0.28  p95     0.52
      draw: rest (clear, sync, GPU wait)     p50    12.71  p95    15.18
      gpu: vertex-buffer upload              p50     4.70  p95     6.06
      gpu: mesh draw (face data + shaded pass) p50    11.40  p95    15.70
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   404.10  p95   419.84  max   525.67 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.11  p95     0.13
    tick (update_viewport)                   p50   354.31  p95   366.78
    on_draw + glFinish                       p50    49.27  p95    59.45
      tick: stage evaluation (mix + skin)    p50   110.92  p95   117.50
      tick: RenderMesh._sync_geometry        p50   226.24  p95   236.55
        of it: face data -> store            p50    23.00  p95    24.69
      draw: viewport render (faces, wire, overlays) p50     4.21  p95     5.14
        of it: face-data upload              p50     0.87  p95     1.17
      draw: gizmo / bones                    p50     6.76  p95     7.39
      draw: HUD                              p50    24.62  p95    27.94
      draw: triad                            p50     0.32  p95     0.57
      draw: rest (clear, sync, GPU wait)     p50    13.01  p95    15.88
      gpu: vertex-buffer upload              p50    33.84  p95    41.38
      gpu: mesh draw (face data + shaded pass) p50    11.36  p95    45.46
    NOTE gpu mesh draw varies 11.18-46.73 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

## Reading (agent, 2026-11-12)

Added after the run; the text above is the run's record and stays as it was. All numbers are **[RPC]**: Q9550 /
9800 GTX, Windows 10, Python 3.14.2, panels off, NVIDIA "prefer maximum performance". "before" = `830f62e`
(worktree, clean), "after" = `1871107` with `src/` tree `559d88b8e2` = `f0a90cc:src` (the "MODIFIED" is the tracked
scene file, outside `src/`). One run per side; the container pairs are in
[`RESULTS_O1_CONTAINER_2026-11-11.md`](RESULTS_O1_CONTAINER_2026-11-11.md).

### One-time costs and memory (`probe_scale_audit.py --only chain`)

| | 87.5k before | 87.5k after | 20k before | 20k after |
|---|---:|---:|---:|---:|
| first weight step (builds the mix surface) | 9,452 ms | **6,149 ms** | 2,218 ms | **1,453 ms** |
| of it: the stage | 3,367 ms | **378 ms** | 852 ms | **103 ms** |
| of it: new RenderMesh | 6,035 ms | 5,729 ms | 1,350 ms | 1,330 ms |
| first pose step (builds the skin surface) | 9,829 ms | **6,672 ms** | 2,403 ms | **1,615 ms** |
| of it: the stage | 2,852 ms | **136 ms** | 708 ms | **31 ms** |
| of it: new RenderMesh | 5,842 ms | 5,770 ms | 1,351 ms | 1,370 ms |
| process memory after both stages | 1,170 MiB | **730 MiB** | 366 MiB | **253 MiB** |

Building the stage surfaces is 9× (mix) and 21× (skin) faster at 87.5k; a first step loses ≈ 3.2–3.3 s of its ≈ 9.5 s.
What remains is the new surface `RenderMesh` (≈ 5.8 s here), not part of O1. Memory with both stages −440 MiB (−38 %).
The ratio to the container differs per row (the old stage build was about as fast here as in the container, the new
mix build 10× slower); compare before / after on one machine.

### D3 frame (`probe_d3_acceptance.py`, 87.5k, 15 %, Morph + Skin), p50 / p95 ms

| Row | frame before | frame after | stage evaluation p50 | `_sync_geometry` p50 |
|---|---:|---:|---:|---:|
| pose wire off | 319.44 / 334.65 | **307.45 / 317.85** | 67.95 → **57.75** | 222.83 → 221.59 |
| weight wire off | 401.01 / 436.74 | **375.16 / 389.26** | 110.56 → **89.85** | 224.03 → 220.48 |
| pose wire ON | 327.69 / 341.81 | **313.35 / 333.55** | 68.85 → **59.26** | 227.70 → 225.87 |
| weight wire ON | 404.10 / 419.84 | **379.47 / 396.85** | 110.92 → **91.09** | 226.24 → 224.56 |

The evaluation is 10 ms (pose, −15 %) and 20 ms (weight, −19 %) faster, the frame 12–14 ms (pose) and 25–26 ms (weight)
at p50; `_sync_geometry` is unchanged (the tuple table reads as fast as the `Mesh`). **D3: OVER** in every row
(p95 318–397 ms, 10–12× the 33.3 ms bar). After O1 a pose frame is ≈ 72 % `_sync_geometry` (normals, neighbourhoods,
mirrors), ≈ 19 % evaluation, ≈ 6 % `on_draw`; the weight rows add the known HUD read-out (24.6 ms) and a GPU
vertex-buffer upload of ≈ 33 ms (4 ms in the pose rows), both the same before O1. The GPU mesh draw is a stable
11.4 ms p50 with maximum performance set; its p95 of ≈ 46 ms in the weight rows is a few slow frames (the probe's NOTE).

### Tests: three explanations above do not hold

- **"138 vs. 152":** 138 is the right count. The 152 in the prompt was the agent's error (it counted
  `tests/test_skinning.py`, 14 tests, instead of the new `tests/test_surface_positions.py`); the container collects 138
  for the same five files. Nothing is collected differently under Python 3.14.
- **"6,555 vs. 6,912 / 183 vs. 8 skipped" — the accounting from the skip list.** In the combined run a module sets
  `pyglet.options["headless"]`; on Windows that needs EGL, which is missing, so every later module that opens a
  `pyglet.window` or a GL context skips. Not collected (189 tests in 7 modules, 7 skip lines): `test_gui_imgui_window`
  16 and `test_gui_menus` 21 (no `imgui-bundle` under 3.14); `test_main_wiring` 39, `test_pyglet_input` 49,
  `test_soft_selection_input` 58 (they set headless themselves: they need EGL and never run on this PC);
  `test_transform_alt_orbit` 5 and `test_scene_menu_local_tmp` 1 (skipped only because an earlier module set
  headless). Skipped at run time (176): 167 "no GL context" — the 165 `test_gl_*` tests (they passed in their own
  process, 165) and `test_main_entry_point` 2 —, 1 test of `test_application_symmetry_cycle` (sets headless), and the
  tests' own 8 skips (the same 8 as in the container). 189 + 167 + 1 = 357 = 6,912 − 6,555. Not run anywhere on this PC
  in this cycle: the 147 EGL-only tests (by design), the 37 imgui tests (Python 3.14), and 7 tests that would run in
  their own process (`test_transform_alt_orbit`, `test_main_entry_point`).
- **The known failure** (`test_scene_menu_local_tmp`) did not run — the module was skipped (above), it is not fixed.
- **`test_hud_strip.py::test_the_triad_ignores_zoom_and_pan_and_perspective`** is not floating-point non-determinism:
  `OrbitCamera.basis()` takes the view direction as `target − eye()` with `eye = target + distance · direction`, so its
  last bits depend on `target` and `distance`. With glibc's `sin` / `cos` the rounding cancels for the test's values,
  with the Windows runtime it does not (1–2 ULP). Deterministic, invisible on screen, and outside O1 (`f0a90cc` touches
  neither `hud.py` nor the camera); whether it failed here before O1 is not known (no earlier full run on this PC). A
  fix of its own: compare with a tolerance, or let `basis()` derive the direction from yaw / pitch.
