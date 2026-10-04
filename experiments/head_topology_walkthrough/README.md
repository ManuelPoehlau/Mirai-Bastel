# Head Topology Walkthrough (Discovery)

**Type B (Research / Discovery). Status: result recorded, not artist-validated. Artist verdict: UNKNOWN.**
Nothing here is production architecture. No file in `src/`, `playground/` or `docs/` (apart from two index links, see below) was changed.

Research document under test: [Character Head Topology — From Box to Deformation-Ready Face](../../docs/research/topology/Character%20Head%20Topology%20From%20Box%20to%20Deformation-Ready%20Face.md)
(Manu, 2026-10-03; sections B to K are reasoned from general practice, not tested). This walkthrough executes its operation chains **D1 to D11**
with the tools that exist today and records, per step, whether the document's prediction held.

## Results (read these)

| File | What |
|---|---|
| [STEP_LOG.md](STEP_LOG.md) | One line per step: id, intent, tool and where it lives, topology vs move, local vs global, planned vs corrective, result (held / deviated / blocked), screenshot. Followed by the measured checks per step. |
| [FINDINGS.md](FINDINGS.md) | Deviations and capability gaps. Observation separated from interpretation. Open questions. |
| [TUTORIAL_DRAFT_DE.md](TUTORIAL_DRAFT_DE.md) | German picture-by-picture draft, **only steps marked held**. |
| `screenshots/` | One PNG per step that worked and made a visible change (poles drawn as red E / blue N discs by the script). |
| `step_log.json` | Machine-readable log; the two Markdown files above are generated from it / written against it. |

Headline (details and numbers in the files): of 48 log lines **32 held, 9 deviated, 7 blocked**. The region-extrude / inset pole predictions held
(E-poles exactly on the patch corners; eye ring 8, mouth ring 12); the budget and counting claims did not (about 10 poles per half counts only E-poles;
the front has a shelf row; the cage is 674 quads, not 300 to 500). Seven steps are blocked by six missing capabilities (delete faces, valence display,
spin edge, subdivision write-back, seam read-out, hinge reference).

## Existence check (stated before starting)

- **What exists:** Playground (`playground/`) is the modelling host: Loop Insert (`loop_insert`), Region Extrude, Loop Slide, Connect/Split/Knife, Edge Loop/Ring selection, Move/Rotate/Scale (src), no symmetry. The Subdivision Lab previews Catmull-Clark but writes nothing back; the Symmetry Lab (production app path) has symmetry but not the Playground's topology tools. There is **no** Inset, Delete Face, Spin Edge or valence display.
- **Rejected earlier / reusable:** nothing was found rejected for these operations. Reusable: "Inset = Extrude with distance 0 + Scale" is already recorded in `docs/research/Extrude_als_Konstruktions-Paradigma_Research_V1.md`; the Playground topology tools and the head asset loader were used as they are.
- **Single Source of Truth:** the research document already lives in `docs/research/topology/`. It is **linked, not merged** into `docs/research/MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` (different scope: that document is the workflow grammar; this one is an operation-chain walkthrough). Index links were added in `docs/research/topology/README.md` and `experiments/README.md`.

## Spike result: can the viewport be captured without manual work?

**Yes**, with a virtual display. Evidence: `screenshots/*.png`, all produced by `run_walkthrough.py` through the real `PlaygroundWindow`.

```bash
pip install pyglet numpy Pillow
xvfb-run -a -s "-screen 0 1280x800x24" python experiments/head_topology_walkthrough/run_walkthrough.py
python experiments/head_topology_walkthrough/render_step_log.py        # rewrites STEP_LOG.md from step_log.json
```

Details: Mesa llvmpipe (GL 4.5) under Xvfb; the window is created normally, three `dispatch_events()` + `on_draw` rounds, VBOs rebuilt after each tool call, buffer read back with `pyglet.image.get_buffer_manager()`.
Note: the existing `playground/_diag_screenshot.py` (one frame, no warm-up) produced an all-black PNG here, as does the committed `playground/_diag_head_view.png`; left untouched. The pure EGL headless mode needs `libEGL`, which this container lacks.

## How the walkthrough was driven (and what that means)

`run_walkthrough.py` calls the **existing tool classes** (`ExtrudeTool`, `LoopSlideTool`, `ScaleTool`, `RotateTool`, `loop_insert`, `MoveOperation`, `edge_loop` / `edge_ring`).
`wt.py` is the thin driver: geometric selection (standing in for mouse clicks), mirroring every one-sided operation by hand (Playground has no symmetry, as instructed), measurement of valence/poles/manifoldness after each step, and screenshots.
Every verdict is computed from a measured value against a quoted claim (`checks` in `step_log.json`). Steps that no tool can do are logged `blocked` and **not** worked around by editing the mesh.
Two read-only probes run on throw-away copies and are marked as such: core `Mesh.remove_face` (to test what the blocked "delete the cap" step would yield) and the Subdivision Lab's `SubdSurface` (preview counts).

Limits: scripted, not hand-driven (UI discoverability and feel untested); crude box blockout (topology, not anatomy); distances and factors are the script's choices.

## Files

- `run_walkthrough.py` — the walkthrough D1 to D11 plus cross-check row X1; writes `step_log.json` and `screenshots/`.
- `wt.py` — driver: tool wrappers, selection helpers, measurement, screenshots.
- `render_step_log.py` — `step_log.json` to `STEP_LOG.md`.

## Not in scope (kept)

No new tools, operations, hotkeys or UI; no changes to `src/` (core stays frozen); no promotion from `experiments/`; the research document was not edited (deviations are in FINDINGS.md; revisiting it is a separate decision, proposal in FINDINGS Q-3); no rigging, morph, sculpt or retopology work.

## Next

Artist: look at [TUTORIAL_DRAFT_DE.md](TUTORIAL_DRAFT_DE.md) and give a verdict (KEEP / ITERATE / REJECT / UNKNOWN) on whether the resulting workflow feels right. Decide whether FINDINGS Q-3 justifies revisiting the research document.
