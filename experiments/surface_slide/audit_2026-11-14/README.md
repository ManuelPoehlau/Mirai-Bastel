# Surface Slide — audit probes (2026-11-14)

Small probes behind the measurements of the
[Production Readiness Audit](../../../docs/research/SURFACE_SLIDE_PRODUCTION_READINESS_AUDIT_2026-11-14.md) that the
research prototype had not measured. They reuse the prototype modules unchanged. `probe_symtri.py` and `probe_capture.py` also *read*
`src/` (`core`, `viewport.derived`, `mirai.scene_factory`) to use Production's own triangulation and mesh; nothing in
`src/` is modified and nothing here is imported by Production. Run from the repo root (NumPy only):

| Probe | Question | Audit section |
|---|---|---|
| `probe_symtri.py` | Is Mirai's drawn triangulation (`viewport.derived.triangulate_face`) mirror-symmetric on the Gollum cage? How far is the drawn surface from its own mirror image? | §3.1 |
| `probe_capture.py` | Production-side capture costs the bench left out: `core.Mesh` → arrays, `triangulate_mesh_face` for every face, reference build, journal write (21 875 / 87 500 vertices) | §3.3 |
| `probe_cursor.py` | Cursor follow of the Move-tool mapping (M1) against a ray / pivot-tangent-plane mapping (M2) on the 18 front-view Gollum drags | §3.4 |
| `probe_thin.py` | Can the pursuit adopt a torn target on the far side of a thin feature (straight-line gap ≤ budget)? | §3.7 |
| `probe_holonomy.py` | Direction jumps of the tree transport between neighbouring vertices on the cage | §3.2 |
| `probe_direct.py` | Direct minimal-rotation transport (no tree) against the tree: frame jumps, distortion, begin cost | §3.2 |

```bash
python experiments/surface_slide/audit_2026-11-14/probe_symtri.py
```

Each probe prints its table; the audit quotes the numbers of the run on 2026-11-14 (container, Python 3.13, NumPy
2.5.3). `probe_capture.py` and `probe_direct.py` take a few minutes.
