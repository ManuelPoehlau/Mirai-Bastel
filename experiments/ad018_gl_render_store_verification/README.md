# AD-018 §5 Implementation — `GLRenderStore` verification

Throwaway evidence scripts for the AD-018 Option B implementation package
(`docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md` §6). Not a Production
entry point (Q6 stays open).

- `run.py` — headless (Xvfb) run: loads `examples/meshes/head_basemesh.obj`,
  binds the Production `OrbitCamera`, drives camera/selection/position/
  topology events through `RenderMesh` + `viewport.gl_render_store.GLRenderStore`,
  prints the four V02 invariants, writes `head_mesh_render.png` as visual
  evidence.
- `run_visible.py` — same scene with a real (non-headless) window, for
  Manu's PC. Optional, not required for the package's Definition of Done.

Run (this environment):

```bash
xvfb-run -a python3 experiments/ad018_gl_render_store_verification/run.py
```

Result (2026-09-25, this sandbox, software GL via Xvfb/Mesa llvmpipe):

```
Loaded head_basemesh.obj: 326 vertices
Initial resource_ids: {'positions': 1, 'normals': 2, 'indices': 3, 'highlight_flags': 4, 'camera_uniforms': 5}
After 20x camera.orbit(): vertex_list identity unchanged = True | resource_ids unchanged = True | geometry_uploads = 0
After selection change: positions/normals ids unchanged = True
After single-vertex move: same VertexList object = True | patched position = (-1.443..., 1.353..., -1.229...)
After edge split: vertex_list identity changed = True | new vertex count = 327
Screenshot written to .../head_mesh_render.png
```

`head_mesh_render.png` shows the shaded head mesh with the selected
vertex's highlight (yellow) visible near the neck — real GL draw through
`RenderMesh.render(camera)` → `GLRenderStore.draw()`, not a parallel path.

See AD-018 §6 for the full completion record.
