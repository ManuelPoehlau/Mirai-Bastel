# GPU Picking Spike (WP-VIEW-PERF-02)

> Discovery spike. Changes nothing under `src/`. Its results feed
> [`AD-022`](../../docs/architecture/AD-022-GPU-PICKING.md) (PROPOSED); per AGENTS.md §5 / M5 they do
> not themselves change `VIEWPORT_V02_ARCHITECTURE.md` §1 / §4.6 (which exclude GPU ID-buffer picking
> for v0.2) or AD-018.

## Question

After the CPU picking slices (`experiments/drag_cost/README.md`, "Result: fix slice 2" and
"Haltepunkt"), every camera change on a 20k mesh still costs ~60 ms of projection before the first
pick, and Manu's verdict asks for Blender-level fluidity (zoom, picking, topology ops on 20k). Can
an ID buffer rendered on the GPU replace that, and how close are its picks to today's?

- **H1 (cost):** a pick after a camera change costs one ID render + a small read-back, far below
  the CPU rebuild, and a hover with a valid render is sub-millisecond.
- **H2 (same picks):** hover/click and Box pick (nearly) what the CPU picker picks; where not,
  the cases can be named.

## Setup

- `id_picker.py` - `GpuIdPicker`: one offscreen framebuffer (3 RGBA8 targets + one depth buffer),
  faces / edges / vertices drawn with their 24-bit ID as colour (`pick_id` vertex attribute, no
  `gl_PrimitiveID`), faces pushed back by `glPolygonOffset(1, 1)` as in the production draw, edges
  and vertices depth-tested against them (Shaded) or not (Wireframe). Two pick variants:
  - **ids:** a pick reads the pixels in the pick radius and decides between the IDs found there by
    the exact screen distance (as the CPU picker); Box = elements with a surviving pixel whose
    corners lie in the box.
  - **depth oracle:** visibility of any point = its window depth against the face depth buffer at
    its pixel; candidates come from the CPU rule (Box: every element with its corners in the box;
    hover: the IDs in the window plus their one-ring), so a pixel holding one ID no longer hides
    the others in it. A face also counts as visible when its own ID is at its centroid's pixel (a
    quad's centroid may lie behind its own triangles; the CPU test excludes the face itself).
- `probe_gpu_picking.py` - the measurement (agreement against production `pick_component` /
  `elements_in_rect`, cost); output is plain ASCII.
- `tests/` - encoding, arguments, import boundary (headless); scenes with a known answer and the
  head mesh against the CPU picker (GL, `xvfb-run -a`).

Run: `python experiments/gpu_picking_spike/probe_gpu_picking.py` (head, body, gollum_20k; ~3 min in
the container), `--assets examples/meshes/gollum.obj --cursors 150 --repeats 8` for 87.5k. Tests:
`xvfb-run -a python -m pytest experiments/gpu_picking_spike/tests` (18 passed).

## Result (container, 2026-10-17)

**Container, not the reference PC** (`REFERENCE_HARDWARE.md` §4): Xeon @ 2.10 GHz, Python 3.13,
**llvmpipe** - the "GPU" render is CPU rasterisation here, so every GPU cost below is pessimistic;
the 9800 GTX draws gollum_20k in 0.56 ms (2026-10-11). Window 1024x768, mesh framed front + back.

**Cost, ms p50** (CPU = production picker after Slice 2):

| | gollum_20k CPU | gollum_20k GPU | 87.5k CPU | 87.5k GPU |
|---|---:|---:|---:|---:|
| pick after an orbit, vertex / edge / face | 74 / 63 / 42 | 17 / 15 / 11 | 227 / 223 / 210 | 49 / 44 / 43 |
| of which: ID render (GL timer) | - | 13 | - | 48 |
| hover pick, valid state, vertex / edge / face | 6.4 / 16 / 2.4 | **0.30 / 0.38 / 0.06** | 32 / 67 / 12 | **0.55 / 0.82 / 0.11** |
| hover, depth-oracle variant | | 0.45 | | 0.77 |
| Box 300 px vertex | 870 | **24** (ids) / 24 (depth) | 6 918 | **78** / 92 |
| build per mesh state (own buffers, Python) | - | 215 | - | 1 073 |

Head / body: everything under 4 ms either way; there the GPU pick after an orbit is no faster than the CPU's (body 2.6 vs 1.8 ms on llvmpipe). **H1 holds** for the read side: hover and Box no
longer depend on the mesh size in Python; what is left after a camera change is the ID render
itself (on llvmpipe 13 / 48 ms, expected ~1-3 ms on the reference GPU - to be measured there).
The spike's own buffers cost 0.2 / 1.1 s to build per mesh state in Python; a production version
would draw from the `RenderMesh` buffers instead (AD-022 option B2).

**Agreement with the CPU picker** (300 integer cursors per camera; `half-px` = the CPU agrees when
asked at the pixel centre, where the GPU samples):

| | body (928 V) | gollum_20k | 87.5k |
|---|---|---|---|
| vertex, Shaded: ids / depth | 99.3 / 99.3 % | 97.8 / **98.7 %** | 90.7 / **96.7 %** |
| edge, Shaded (ids) | 99.5 % | 96.3 % | 89.3 % |
| face (ids) | 97.8 % + 1.5 % half-px | 86.7 % + 13.2 % half-px (1 real in 600) | 78.7 % + 21.3 % half-px (0 real) |
| vertex, Wireframe: ids / depth | 100 / 100 % | 97.0 / **100 %** | 86.3 / **98.3 %** |
| edge, Wireframe (ids) | 100 % | 92.3 % | 79.0 % |

Every "real" difference is another element right next to the CPU's (no case of "GPU none, CPU
something" on the dense meshes): the neighbouring vertex / edge that shares the pixel. On 87.5k
framed whole, vertices are less than a pixel apart, so the "nearest" one is not something the eye
can tell apart either.

**Box Select** (count CPU | ids variant -only CPU +only GPU | depth variant, front camera):

| | CPU | ids | depth |
|---|---:|---|---|
| gollum_20k 60 px, vertex / edge / face | 169 / 299 / 131 | -9 / -29 / -2 | **identical** |
| gollum_20k 300 px, edge | 12 455 | -1 350 +208 | -91 +372 (3.7 %) |
| 87.5k 300 px, edge | 49 720 | **-16 348** +312 | -303 +1 715 (4.0 %) |
| body 300 px, face | 124 | -3 +38 | -2 +1 |

The **ids variant loses up to a third of a dense Box** (one ID per pixel) and adds partly visible
elements at the silhouette; the **depth variant keeps the CPU rule** within 0-4 % (more permissive:
the polygon-offset tolerance lets grazing elements through), at the same cost.

**H2: partly.** Hover/click: 97-99 % identical on the editing sizes, the rest is the neighbour in
the same pixel; face picks differ only by the half-pixel sampling convention (the CPU samples the
pixel corner, the GPU its centre - a convention to choose, not an error). Box: only the depth
variant is acceptable; it is not bit-identical (0-4 % at the edges of visibility), so an Artist
check is needed. Neither variant can be proven equivalent the way Slices 1 and 2 were.

## Result: reference PC (Manu, 2026-10-20)

Core 2 Quad Q9550, GeForce 9800 GTX, Windows 10, Python 3.14.2, `GL_VERSION` 3.3.0, hidden 1024x768 window.
Raw output: [`RESULTS_REFERENCE_PC_2026-10-20.md`](RESULTS_REFERENCE_PC_2026-10-20.md). ms p50 (the `cpu` column is the
production picker after WP-VIEW-PERF-01 slices 1 and 2). **[RPC]** numbers; the container table above stays valid as the
llvmpipe comparison.

| | gollum_20k CPU | gollum_20k GPU | 87.5k CPU | 87.5k GPU |
|---|---:|---:|---:|---:|
| pick after an orbit, vertex / edge / face | 160.9 / 187.7 / 150.2 | **3.3 / 3.75 / 2.4** | 661.9 / 774.5 / 618.7 | **14.0 / 15.5 / 11.8** |
| hover pick, valid state, vertex / edge / face | 18.6 / 43.4 / 8.0 | **1.65 / 1.96 / 0.71** | 85.2 / 197.4 / 35.2 | **3.3 / 4.1 / 0.65** |
| Box 300 px vertex | 2 384 | **89** (depth variant 85) | 14 522 | **295** (depth variant 332) |
| ID render, GL timer (GPU time) / wall | - | 1.14 / 1.43 | - | 10.3 / 10.8 |
| build of the spike's own buffers per mesh state (option B1, Python) | - | 795 | - | 3 087 |

Head and body: every GPU pick row of the `ids` variant is under 4 ms (the depth variant up to 6.3 ms); the GPU hover is not faster than the CPU hover there (head vertex 0.85 vs
0.21 ms), after an orbit the body is 1.6 vs 6.6 ms.

Agreement with the CPU picker (Shaded): vertex 97.7 % (depth oracle 98.7 %) on gollum_20k and 90.7 % (96.7 %) on 87.5k;
edge 96.3 % / 89.0 %; face 86.7 % + 13.2 % half-pixel / 78.7 % + 21.3 % half-pixel (no "real" face difference on 87.5k).
Box 300 px edge, front camera: variant `ids` 11 315 vs CPU 12 455 (gollum_20k) and 33 693 vs 49 720 (87.5k); depth variant
-91 / +373 and -303 / +1 713. The container pattern of the table above repeats.

**What this answers from "What this does not answer":** the reference-PC cost (an ID render of 1.14 ms GPU time on
gollum_20k, 10.3 ms on 87.5k; FBO, `glReadPixels` and the GL timer query ran without error on the GL 3.3.0 driver), and
the Box/hover behaviour at 87.5k. **Still open:** Knife, Paint, object picking, snapping, placed objects, resize, W drags;
p95 and outliers (p50 of 8-15 samples only); the interaction with H7 surfaces (SubD, Morph) shown instead of the cage.

**`gl_PrimitiveID` (step 4 of the practical test), Manu 2026-10-20, in chat:** "Das Flat Shading sieht auch gut aus
(keine Flecken)." Recorded by the agent on Manu's instruction. It answers the check asked for in step 4 for **Flat**;
Smooth and the other B3 verdicts (triangles, light, performance) were not part of the answer and stay as they are in the
[Intake Log](../../docs/architecture/WP-06_INTAKE_LOG.md). Evidence for AD-022 option B2, not a decision.

## What this does not answer

- Reference-PC cost: the ID render + `glReadPixels` stall on the 9800 GTX / its driver (Manu's run).
- `gl_PrimitiveID`: the spike avoids it; option B2 of AD-022 needs it (the Flat shading uses it
  since 2026-10-15 - if Flat looks right on Manu's PC, that is evidence).
- Knife (`knife_pick`: vertex / edge / face snap + `t` + hit position), Paint, object picking and
  snapping: not built here; they are candidates + exact CPU math on the few elements found, the
  same pattern as `pick_vertex` / `pick_edge`.
- Placed objects (model matrix), window resize, W drags (positions change per move: the ID
  buffers need the same patching as the draw buffers).

## Praktischer Test für Manu (Referenz-PC, ca. 10 Minuten)

1. `git pull`
2. `python experiments/gpu_picking_spike/probe_gpu_picking.py` - öffnet kein Fenster, ~2-5 Minuten.
   **Die ganze Ausgabe** (ab `GPU ID-buffer picking vs CPU picker`) in den Chat kopieren.
3. Kurzvariante 87.5k: `python experiments/gpu_picking_spike/probe_gpu_picking.py --assets examples/meshes/gollum.obj --cursors 150 --repeats 8` - Ausgabe ebenfalls kopieren.
4. Im Fenster `python src/main.py examples/meshes/gollum_20k.obj`, Taste `D` bis Flat Shading: sieht
   jede Fläche einheitlich hell aus (pro Polygon, keine Flecken)? Ein Satz dazu reicht - das
   beantwortet, ob dein Treiber `gl_PrimitiveID` zuverlässig liefert.
