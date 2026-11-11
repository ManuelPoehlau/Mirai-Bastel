# Architecture and Performance Audit — the Mesh Architecture Before Further Scaling

**Status:** Discovery, evidence and a recommendation — **no decision, no production code changed.** First-pass record as
delivered on 2026-11-10 (AGENTS.md §6: not edited afterwards to agree with later decisions; later changes go into dated
addenda at the end).
**State audited:** `5b65c62` (2026-11-10, branch `claude/happy-hopper-dogeh3`). The pose-step path (`src/viewport`,
`src/mirai/skinning.py`, `src/mirai/morph_mix.py`, `src/core/mesh.py`) has no commit since `2ee2061`, the state of the
2026-11-07 reference-PC run **[V]** — those reference-PC numbers describe the audited code.
**Question:** can the existing architecture be evolved to interactive modeling and deformation of a character base mesh
of about 100,000 polygon faces on the reference PC, without losing what already works?
**Labels:** **[RPC]** measured on the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX, taken from the repository's
result files, none measured by this audit) · **[C]** measured for this audit in a cloud container (Intel Xeon 2.1 GHz,
4 logical cores, Linux, Python 3.13.18, Mesa llvmpipe = software GL; draw times there are **not** GPU times) · **[H]**
estimate or extrapolation, never a measurement · **[V]** verified in code or by a test run during the audit.
**Container → reference PC:** for the same probe and the same code, the Python parts ran **2.3–3.5× slower** on the
reference PC than in this container (pose step, [RPC] 2026-11-07 against [C] 2026-11-10 / 11) and 2.0–2.9× slower for
the W drag ([RPC] 2026-10-21, an older commit). The container itself varied by up to 40 % between two hosts for the
same row. Where an [H] figure for the reference PC is given, it is the [C] value × 3. Nothing is known about the ratio for NumPy or native code on that CPU; those [H] figures are marked separately.
**Counts used:** the reference mesh `gollum_20k.obj` has 21,875 vertices and 21,875 quads (43,750 triangles). The dense
mesh is the same mesh after one Catmull-Clark step: **87,500 vertices, 87,500 quads, 175,000 edges, 175,000
triangles** — "about 100k base faces" in this report means this mesh unless a number is scaled (× 1.14) and marked [H].
"Region" is the share of base vertices an operation moves. Base faces, evaluated (SubD) faces, triangles and moved
vertices are kept apart throughout.
**Brief:** the task text received ends in the middle of its §6; this report covers §1–§6 and adds a recommendation.
**Builds on:** [MESH_ARCHITECTURE_AUDIT_2026-10-27](MESH_ARCHITECTURE_AUDIT_2026-10-27.md) (provenance, layers — since
implemented as AD-025 / AD-028) and the probes in [`experiments/drag_cost/`](../../../experiments/drag_cost/README.md).

---

## Kurzfassung für Manu (Deutsch)

- **Antwort:** Ja, die Architektur trägt das Ziel — aber nicht mit der heutigen Art, das verformte Mesh zu berechnen und
  anzuzeigen. Der Kern (Mesh, IDs, Änderungs-Journal, Punkt-Layer für Morphs und Gewichte, Undo) ist nicht der Engpass
  und muss nicht neu gebaut werden. Alles, was heute an Modellieren + Morph + Skin + SubD zusammen funktioniert, hängt an
  diesem Kern und bleibt unberührt.
- **Der Engpass** ist die Schicht dahinter: jede Stufe (Morph-Mix, Skin, SubD) hält ihr Ergebnis als komplette Kopie des
  Mesh aus Python-Objekten, und die Anzeige rechnet pro bewegtem Punkt in Python Normalen und schreibt pro Fläche 36
  Zahlen neu. Das kostet auf dem Referenz-PC etwa 30 µs pro bewegtem Punkt (gemessen), egal wie schnell die eigentliche
  Verformung ist.
- **Gemessen (Container, nicht dein PC):** dieselben Rechnungen auf kompakten Zahlen-Arrays statt Python-Objekten sind
  mit NumPy 4–25× schneller, mit einem kleinen C-Kern meist über 100× schneller — mit denselben Ergebnissen (Skin und
  Morph bit-gleich, Normalen bis auf Rundung in der 14. Stelle). Die Hardware ist also nicht das Problem.
- **Was das für 100k heißt (Schätzung):** heute würde eine Pose über das ganze Mesh auf deinem PC etwa 3 Sekunden pro
  Mausschritt brauchen, ein Kiefer-Bereich (15 %) etwa eine halbe Sekunde. Mit Arrays + NumPy: etwa 0,35 s bzw. 80 ms.
  Mit C-Kern: etwa 20 ms bzw. wenige ms.
- **Kleine Bearbeitungen bleiben schnell:** Extrude, Knife, Delete, Undo und das Ziehen weniger hundert Punkte hängen
  schon heute fast nicht von der Mesh-Größe ab.
- **Live-Symmetrie hat eine eigene Grenze:** die Zuordnung „welcher Punkt gehört zu welchem Spiegelpunkt“ wird bei jedem
  Geste-Beginn für das ganze Mesh neu berechnet (Container: 0,5 s bei 87,5k pro Berechnung).
- **Zwei Dinge sind schon heute unnötig langsam** (unabhängig von der großen Frage): mit eingeschaltetem Drahtgitter
  wird bei jeder Bewegung das ganze Gitter neu gebaut, und der erste Hover nach dem Drehen im Punkt-/Kanten-Modus rechnet
  wieder das ganze Mesh durch (das war im Oktober schon behoben und ist zurückgekommen).
- **Außerdem gefunden:** `tests/test_scene_menu_local_tmp.py` (laut eigenem Kommentar „nicht committen“) liegt im
  Repository und schlägt fehl; dadurch ist `pytest tests` rot. Ich habe die Datei nicht angefasst.
- **Was ich von dir brauche:** die Messläufe auf deinem PC (vier Befehle in §J) und die Entscheidung, ob NumPy (unter
  Python 3.12) eine feste Abhängigkeit werden darf (§H).

---

## A. Verdict

1. **The Core is not the ceiling and does not need a rewrite.** Topology edits, history and the journal are local at
   87.5k faces: a single-element Extrude / Knife / Dissolve / Delete and its Undo cost about the same Python time as at
   20k **[C]**; a W drag of 36–500 vertices costs the same at 87.5k as at 20k **[C]**. The semantic machinery that makes
   Mirai's combinations work — stable IDs, the change journal, point layers with origin interpolation, the
   "declaration = support" gate — lives entirely in the Core and its callers and is untouched by everything below.
2. **The ceiling is structural, and it sits in two places behind the Core:**
   - **Evaluation results are `core.Mesh` object graphs.** Each stage (morph mix, skin, SubD) owns a complete mesh copy
     with its own topology, written one vertex at a time through `set_vertex_position`, and hands change sets to the
     next stage as Python sets of IDs. Per stage at 87.5k: about +450–490 MiB process memory and 6–7 s to build it the
     first time **[C]**.
   - **The viewport's derived data is per-element Python work on a denormalised layout.** Per moved vertex it
     recomputes normals through dict lookups and rewrites, for every adjacent face, a 36-float row holding copies of
     the corner positions and normals: 168–183 bytes handed to the store per moved vertex **[C]**. This is the
     73–77 % of a pose step measured on the reference PC **[RPC]**, reproduced here as 73–79 % **[C]**.
   Both scale with the number of *moved* vertices, not with mesh size — which is why local edits are fine and
   deformation of regions is not.
3. **The same computations on packed arrays are 4–25× (NumPy) and mostly more than 100× (native C, compiled for the
   Core 2's instruction set) faster in the container, with the same results** — bit-identical for skin and morph,
   equal to rounding (≤ 3·10⁻¹⁴) for normals and stencils (§E.5) **[C]**. The cost is the per-element
   interpreter work, not the arithmetic and not the hardware. AD-023's note that NumPy was "not pursued because the
   dominant cost is a Python-object mesh, not arithmetic" was right about the cause and is the reason arrays help: the
   object mesh is exactly what the array form removes from the hot path.
4. **A targeted intervention is justified; a rewrite is not.** The three layers the brief asks about (authoritative
   Core / evaluation / derived viewport geometry) already exist as responsibilities with the right seams (§G.1). What
   is missing is a compact numerical *representation* flowing across those seams. Recommended direction (§H): keep the
   Core as it is; let evaluation stages produce positions over the base mesh's topology instead of mesh copies; let the
   viewport read arrays and stop duplicating vertex data per face; run the kernels in NumPy, with a small native kernel
   only if a reference-PC measurement shows NumPy is not enough.
5. **What stays out of reach on the reference PC regardless of architecture [H]:** SubD of a 100k-face cage is 400k
   faces / 800k triangles per frame — a GPU load the 9800 GTX is unlikely to draw fluidly (the ID pass alone took
   10.3 ms at 175k triangles **[RPC]**). 100k *base* faces is a reasonable target; 100k base faces *with SubD on* is
   not, on that card.

---

## B. What must be preserved — inventory against code and tests

Run for this audit **[V]**: `xvfb-run -a python -m pytest tests -q` → **6,888 passed, 1 failed, 8 skipped, 68 subtests
passed** (13 min 44 s); `xvfb-run -a python -m pytest tests/test_gl_*.py -q` (own process) → **138 passed**;
`experiments/drag_cost/tests` → **73 passed** (with this audit's new test file). Not run: `experiments/morph_lab/tests`, `experiments/knife_oracle/tests` (no `src/` change in this audit).
The one failure is `tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring`: a file whose own docstring says
"TEMPORÄRER lokaler Probe (wird gelöscht, nicht committen)", in git since the bulk commit `ac4651e`. It fails alone
and without this audit's changes (`interaction_owner` is None where it expects `"transform"` after a W key press) and
tests none of the capabilities below; left as found (§I.7).

"Automated" below means a test at HEAD exercises the behaviour through `Application` or the stage itself. "Manual
only" means the repository holds an Artist verdict but no test of that property.

| Capability | Where it lives | Automated at HEAD | Manual only / not covered |
|---|---|---|---|
| Topology ops (Extrude, Knife, Dissolve, Delete, Split, Connect, Collapse, Bevel, Loop Slide) | `src/core/mesh.py` primitives, `src/mirai/topology/` | `test_topology_mutations.py`, `test_mesh_change_journal.py` (random sequences against a snapshot oracle), Knife suites, `tests/mesh_invariants.py` | feel / speed |
| Attach / Detach / Select Linked / Weld / Bridge (AD-031) | `src/mirai/mesh_assembly.py`, `topology/weld.py` | `test_attach.py` 16, `test_detach.py` 20, `test_weld.py` 24, `test_bridge.py` 12, `test_symmetric_weld_bridge.py` 12, GL variants | — |
| Modeling with active morph targets; topology edits keep target correspondence | origin interpolation inside the Core primitives (`add_vertex(origin=)`, `split_edge`, `split_face`, `collapse_edge`), gate `src/mirai/layer_declarations.py` | `test_layer_topology_ops.py` 11 (each declared operation against its analytic rule), `test_layer_knife.py` 9, `test_layer_gate.py` 17 (every command classed), `test_morph_multi.py::test_every_phase5_operation_with_three_targets_in_the_app` (plain and symmetric), `…::test_the_knife_with_three_targets_in_the_app` | visual quality of interpolated loops in bent areas |
| Persistent targets, Base / Target / Mix, exact Undo, save / load | `src/mirai/morph_targets.py`, `morph_mix.py` | `test_morph_targets.py` 29, `test_morph_multi.py` 23 (mix == definition through random edits; independent of weight-step order; bit-exact after save → load) | — |
| Picking / hover on the evaluated morph surface | `Viewport.set_cage_source`, `Application._query_mesh` | `test_morph_picking.py` 18 (incl. Box / Lasso / Paint, Knife and symmetric Knife on the mix), `test_gl_morph_picking.py` 7 | — |
| Live Symmetry (moves, transforms, topology), Re-Symmetry | `src/mirai/symmetry*.py`, `symmetric_ops.py`, `controllers/symmetry.py` | `test_symmetric_*.py` (11 files), `test_application_symmetry*.py`, `test_resymmetrize.py` 8, `test_application_resymmetrize.py` 39, `test_symmetry_fail_closed_guard.py` | Re-Symmetry is declared position-only for layers (`layer_declarations.py:184`), but no test runs it on a mesh that carries targets or weights **[V, by grep]** |
| Soft Selection, geodesic, symmetric | `src/mirai/soft_selection/`, weighted transforms in `core/operations/transform.py` | `test_soft_selection_*.py`, `test_symmetric_soft_selection.py` 27, `test_application_soft_symmetry.py` 5 | — |
| Skeleton, weights, binding | `src/core/rig.py`, WEIGHTS layer in `core/mesh.py`, `src/mirai/skin_weights.py`, `controllers/skeleton.py` | `test_rig.py` 12, `test_weights_layer.py` 26, `test_skin_weights.py` 9, `test_application_rig.py` 19 (weight gestures with Soft, symmetry, mask) | — |
| Topology edits on a weighted mesh | same primitives, WEIGHTS kind | `test_weights_topology_ops.py` 13 (every declared entry covered; Knife variants) | mirror copy of a weighted mesh is *refused* by design (`test_mirror_copy_of_a_weighted_mesh_is_refused_untouched`) |
| Morph + skin evaluated together | `src/mirai/skinning.py` (`SkinSurface`), `surface_chain.py` | `test_skin_stage.py`: randomized oracle (pose steps, weight writes, base moves, topology edits, morph steps, bone add / delete, Undo / Redo) bit-exact against the definition; order independence | — |
| Editing / selecting while deformed | picking stays on the rest cage while posed, on the mix while a target is dialled in | `test_skin_stage.py::test_picking_and_the_edit_mesh_stay_at_rest`, `test_morph_picking.py::test_posed_keeps_picking_on_the_rest_cage` | — |
| Catmull-Clark, stencils, local updates | `src/mirai/subdivision/` | `test_subdivision_exact.py` 9, `test_subdivision_stencils.py` 7 (stencils == independent recursive CC; local == full), `test_subdivision_app.py` 31 (W/E/R, Tweak, Soft, symmetry, Extrude, Split, Knife, Dissolve, Delete, Undo, in-place patch) | — |
| SubD in the chain | `SurfaceChain` | `test_morph_multi.py::test_morph_and_subd_show_together_as_subd_of_the_mixed_cage`, `test_skin_stage.py::test_morph_skin_subd_is_subd_of_the_skinned_mix` | — |
| Incremental viewport == full rebuild | `src/viewport/render_mesh.py` | `test_render_mesh_incremental.py` 5 (patch equals rebuild per element) | — |

**Reading.** The combinations the brief lists are covered by tests that compare against a *definition* (an oracle
function), several of them randomized. That is the asset that makes an internal change of representation safe: every
stage already has an exact reference (`morph_mix.evaluate`, `skinning.evaluate`, `SubdLevel.apply_full`) and tests that
demand bit-identical output. The prototype kernels of §E.5 meet those definitions bit for bit (skin, morph) or to rounding
(stencils 3·10⁻¹⁶, normals ≤ 3·10⁻¹⁴).

**Limits found in the inventory [V]:** the SubD preview refuses any surface above 25,000 derived faces
(`MAX_DERIVED_FACES`, `subdivision/preview.py:75`, "not a measured limit of the reference PC") — `gollum_20k` cannot
show SubD at level 1 today, so "SubD on a dense character" is not an existing capability that could be lost; it does
not exist yet above ~6,000 base quads at level 1.

---

## C. The architecture as built

### C.1 Data flow (class and file names at `5b65c62`)

```
 tools / commands  ──►  core.Mesh  (src/core/mesh.py)                      AUTHORITATIVE, saved, in History
                        _vertices / _edges / _faces: dict[Id -> dataclass]  (mesh.py:505-507)
                        _edge_lookup, _vertex_edges (adjacency indices)     (mesh.py:511-515)
                        point layers: PackedValues / PackedWeights over one LayerSlots map (layer_storage.py)
                        face-corner UVs, face regions, symmetry definition
                        every write calls _touch_* -> all active MeshChange journals (mesh.py:580-607)
                              │ MeshDelta -> MeshDeltaCommand -> HistoryStack   (Undo / Redo, exact, O(changed))
                              │ MeshWatch (keys only) per consumer
          ┌───────────────────┼──────────────────────────────┬─────────────────────────┐
          ▼                   ▼                              ▼                         ▼
 RenderMesh(edit mesh)   MixSurface (morph_mix.py:88)    PickCache                 regions, hidden,
 always kept in sync     .mesh = a full core.Mesh copy   (picking_cache.py)        symmetry state …
                         p = b + Σ wᵢ·dᵢ per candidate
                              │ its own journal (MeshWatch)
                              ▼
                         SkinSurface (skinning.py:255)
                         .mesh = a second full core.Mesh copy, LBS per candidate
                              │ its own journal
                              ▼
                         SubdSurfaceProvider (subdivision/preview.py:99)
                         SubdSurface: topology + composed stencils (catmull_clark.py)
                         .surface_mesh = a third core.Mesh (derived topology)
                              │ `moved` set of VertexIds / surface_topology_changed   (H7 contract)
                              ▼
 SurfaceChain / ChainedSurface (surface_chain.py)  ──►  Viewport.surface_provider  (the single H7 slot)
                              ▼
 RenderMesh(surface mesh)  (render_mesh.py)   + RenderMesh(cage) for ID picking when the cage is not the surface
   DerivedGeometry: dict vertex_to_faces / face_normals / vertex_normals   (derived.py:221)
   slot layout: VertexId -> buffer slot, face rows, triangle slots, spare capacity
   CPU mirrors array('f') positions / normals
                              ▼
 GLRenderStore (gl_render_store.py): a third copy as Python lists (_cpu), pyglet VertexList,
   texture buffers `face_shading` (36 floats per face) and `triangle_faces`; draw, GPU ID picking
```

`Application.update_viewport` (`application.py:5218`) runs `skin.refresh()`, `morph.refresh()`, then
`Viewport.sync()` (`viewport.py:842`), which syncs the edit `RenderMesh`, then the provider chain and the surface
`RenderMesh`, then overlays and the wire.

### C.2 The seven questions

1. **Where authoritative data lives.** Only in `core.Mesh` (per scene object) and `Scene.rig`: topology, positions (the
   rest shape), morph offsets and skin weights as point layers, UVs, regions, symmetry definition. Weights of morph
   targets and the pose are view state (not saved, not in History).
2. **What is derived.** (a) per stage an evaluated `core.Mesh` with the input's IDs and topology (mix, skin) or its own
   (SubD); (b) per shown mesh a `RenderMesh` with `DerivedGeometry` (adjacency, normals, bounds), slot maps and
   `array('f')` mirrors; (c) the store's Python-list copies and GL buffers; (d) `PickCache` screen projections;
   (e) overlay vertex lists (wire, selection, soft bands, SubD lines).
3. **One vertex changes (W drag).** `Mesh.set_vertex_position` → `_touch_v` records the before-position in every
   active journal (History recording + one watch per consumer). `Viewport.on_vertices_moved` marks the edit
   `RenderMesh`. Next sync: `RenderMesh._sync_geometry` (`render_mesh.py:1047`) → faces around the vertex get new
   Newell normals, the 1-ring vertices new vertex normals (`derived.py:295-346`), positions and normals go through the
   mirrors to the store, and every face touching a changed vertex gets its 36-float row rebuilt and re-sent. If a stage
   is active it sees the vertex in its watch, recomputes that vertex from its inputs (never incrementally — the drift
   guard) and reports it as moved; the surface `RenderMesh` then repeats the same normal / row work for the surface.
   With the wire shown, `Viewport._sync_edges` (`viewport.py:919`) rebuilds the segment list of **all** edges.
4. **Topology changes.** The primitive touches the affected vertices / edges / faces (journal), writes interpolated
   layer values for new vertices at mutation time, and `_mesh_transaction` (`application.py:3856`) turns the journal
   into one `MeshDeltaCommand`. `RenderMesh._patch_topology` (`render_mesh.py:790`) patches slots, triangles, normals
   and rows for the journal's elements only (full rebuild when > 25 % changed, the spare slots run out, or the mesh has
   < 2,048 elements). Mix and skin replay the same element records on their own mesh copies
   (`morph_mix._topology_delta`). SubD compares a whole-mesh signature (`preview.py:82`, O(V+E+F)), rebuilds topology
   and **all** stencils, then patches its derived mesh in place by stable keys.
5. **Propagation morph → skin → SubD.** Pull-based, once per frame, in stage order (`ChainedSurface.sync`,
   `surface_chain.py:47`). Each stage reads the previous stage's mesh object and its journal; a weight step produces
   the target's points as candidates (sparse), a pose step the points of the bones whose transform changed (a bone →
   points index), SubD the derived vertices whose stencils reference a changed control vertex (`apply_local`, or
   `apply_full` above 12.5 % changed). Each stage is a pure function of its current inputs; tests pin this.
6. **What the viewport receives.** A mesh object plus either "these VertexIds moved" or "topology changed, read the
   journal". It never receives arrays; it pulls every position through `mesh.vertex_position(id)`.
7. **Caches and their invalidation.** `DerivedGeometry` normals: by 1-ring of moved vertices. Bounds: lazy, O(V) on
   next read. Triangulation: per face, re-done at the next topology sync for faces around vertices moved since
   (`_retriangulate`). `PickCache`: patched from the journal for the same view, **fully re-projected on every camera
   change** (`picking_cache.py:124`). Mix offset caches: by layer journal keys. Skin bone → points index: by weights
   journal. SubD stencils: by topology signature (global). GPU picker ID buffers: by `content_revision` / camera.

### C.3 What this structure costs per element [C]

| Structure, 87.5k faces | Memory | Build |
|---|---:|---:|
| `core.Mesh` (traced Python allocations) | 157 MiB | 1.1–1.2 s from arrays; `export_state` 0.77 s; `Mesh.from_state` 2.9–3.4 s |
| `RenderMesh` incl. `DerivedGeometry` and the store's list copies, without GL | 190 MiB | 2.4–3.3 s |
| The same information as packed arrays (positions, corner CSR, vertex→face CSR, both normal sets, float32 mirrors) | 12 MiB | 0.05–0.15 s incl. all normals |
| Whole process, scene loaded, first frame | 570 MiB | 4.5–5.9 s |
| + morph mix shown | +488 MiB | 6.4–6.9 s for the first weight step |
| + skin stage shown | +454 MiB (1.53 GB in total) | 5.9–6.3 s for the first pose step |
| Scene file | 44 MiB JSON | save 1.0–1.1 s, parse 3.8–4.1 s |

On the reference PC the times are about 3× these **[H]** (first weight step ≈ 20 s, first pose step ≈ 18 s, load
≈ 14–18 s); the memory is the same order (8 GB hold it, three or four stages on two objects would not be comfortable).

---

## D. Existing evidence, re-verified

| Claim in the repository | Source | Status at `5b65c62` |
|---|---|---|
| Pose step on `gollum_20k`: 35 / 99 / 698 ms p50 at 5 / 15 / 100 % region (p95 59 / 109 / 837) | `RESULTS_SKIN_IMGUI_REFERENCE_PC_2026-11-07.md` M1 **[RPC]** | **Holds** — no code change on that path since **[V]**. Scenario: lowest-Y share of the points, 70 % on one bone, 30 % shared with its child; one mouse move in pose mode + `update_viewport`, draw excluded. |
| `_sync_geometry` is 73–77 % of the pose step, LBS 14–16 %; GPU skinning alone would not help | same file, M3 **[RPC]**; AD-028 §5.4 | **Confirmed [C]:** 73–79 % and 14–22 % (§E.3). The new split shows *what* inside it: face rows 23–26 % of the step, face normals 16–20 %, vertex normals ~10 %, positions + normals 9–15 %, neighbourhood sets 5–7 %. The actual GPU transfer is < 1 %. |
| W drag: ≈ 27 µs per moved vertex, sync 88 % of the move (3,339 V: 91 ms) | `RESULTS_DRAG_BATCHED_REFERENCE_PC_2026-10-21.md` **[RPC]** | **Holds in shape [C]:** sync 85 % of the move; cost follows moved vertices and is independent of mesh size (500 V: 7.5 ms at 20k, 9.2 ms at 87.5k). |
| Soft Selection: plain fine, symmetric / large radius over the bar | AD-020 §7, drag_cost README **[RPC]** 2026-10-11 / 10-15 | **Bottleneck today is the same viewport sync, not the influence [C]:** per move, sync is 82–86 % (§E.2). The influence is paid once per gesture and once per selection click with Soft on, and that part grows with density (the same radius holds 4× the vertices: 16 → 93–105 ms per preview at 20k → 87.5k). Symmetric rows were not re-measured at 20k+ (no symmetric dense asset). |
| Topology ops on 20k cost 1.6–3.6 s; one structural rebuild ≈ 1.26 s | AD-023 §1, `RESULTS_TOPOLOGY_REFERENCE_PC_2026-10-20.md` **[RPC]** | **Superseded.** AD-023 V1 + H1 are implemented; single-element ops are local (§E.6). Do not quote these numbers as current. |
| "GPU first pick after an orbit: vertex / edge / face 6.9 / 8.2 / 3.8 ms" | AD-022 §11, `RESULTS_PICKING_APP_REFERENCE_PC_2026-10-21.md` **[RPC]** | **Regressed for vertex and edge [C]:** the same probe gave 16 / 21 / 11 ms in a container on 2026-10-21 and gives 77 / 104 / 11.5 ms now. `gpu_pick_component` calls `PickCache.refresh` for vertex and edge mode (`gpu_picking.py:46-47`), which re-projects every vertex and face after a camera change. §I.1. |
| SubD timings (head / body, one moved cage vertex) | `src/mirai/subdivision/README.md` **[C]** 2026-10-23 | Still container-only. Reference-PC SubD rows exist only as part of the pose-step table (SubD L2 on head: 33 / 53 / 161 ms p50) **[RPC]**. |
| `examples/meshes/gollum.obj` has 87,500 V | `REFERENCE_HARDWARE.md` §2 note 2026-10-17 | **No longer true [V]:** the file is byte-identical to `gollum_20k.obj` (21,875 V). The repository has no dense asset; `probe_morph_gl.MEMORY_ASSETS` and `probe_navigation_gl.GOLLUM` still point at it as the dense one. |
| Rule of thumb "reference PC ≈ 2× container" | `REFERENCE_HARDWARE.md` §2 | Too low for this container: 2.3–3.5× on the pose step. Use the same-day, same-probe ratio, not a constant. |

---

## E. Measurements

### E.1 Method

Existing probes where they exist (`probe_navigation_gl.py`, `probe_skin_split.py`, `probe_picking_app.py` after the
accessor fix of §I.4), run at 20k and 87.5k; two new probes for what was missing: `probe_scale_audit.py` (the pose-step split, one-time
stage costs, process memory) and `probe_kernels.py` + `kernels_native.c` (production code against packed arrays, no
GL). All go through `Application` → `Viewport` → `GLRenderStore` exactly as the window does, except the kernel probe
(CPU side, `TraceStore`). Raw outputs: §L. Every [C] number below is p50 unless stated. The container was restarted
once during the audit (a different host); rows measured on both hosts differ by up to 40 % and are given as ranges.
Shares of a step were stable across both.

### E.2 Per-step costs through the application [C]; reference-PC values where the repository has them

| Per mouse step | 20k [RPC] | 20k [C] | 87.5k [C] | scales with |
|---|---:|---:|---:|---|
| Orbit, sync part (draw excluded) | — | 0.04 ms | 0.06 ms | nothing (no per-frame mesh work) |
| W drag 36 V | 2.3 | 0.97 | 1.34 | moved vertices |
| W drag 112 V | 4.9 | 2.44 | 2.57 | moved vertices |
| W drag 500 V | 14.6 | 7.49 | 9.16 | moved vertices |
| W drag 500 V, **wire overlay on** | — | — | **144** | **all edges** (175,000) |
| Soft W, 15 % radius geodesic | 15.3 (508 V) | 5.26 (508 V) | 23.2 (1,921 V) | moved vertices |
| Soft W, 50 % radius geodesic | 91.3 (3,339 V) | 32.0 (3,339 V) | 171 (13,195 V) | moved vertices |
| Pose step, 5 % region | 35.3 | 10–13 (1,093 V) | 68 (4,375 V) | moved vertices |
| Pose step, 15 % region | 99.4 | 30–43 (3,281 V) | 139–177 (13,125 V) | moved vertices |
| Pose step, 100 % region | 698 | 235 (21,875 V) | 920–940 (87,500 V) | moved vertices |
| Pose step, 15 %, wire on | — | 56–94 | 257–393 | moved vertices + all edges |
| Hover move (vertex mode, camera still) | 2.2 | 1.1 + sync 0.9 | 2.8 + sync 3.8 | highlight buffer: all vertices (§I.3) |
| First hover after a camera move, vertex / edge | 6.9 / 8.2 (2026-10-21) | 77 / 104 | 421 / 303 | all vertices + faces (§I.1) |
| First hover after a camera move, face | 3.8 | 11.5 | 45 | software ID render here; GPU on the reference PC |

Per moved vertex the application path costs ≈ 9–14 µs **[C]** and ≈ 27–30 µs **[RPC]** (99 ms / 3,281 V; 91 ms /
3,339 V), of which the display side is three quarters.

Where a cell holds a range, it is two runs of the same row on two container hosts (§E.1).

**Extrapolation to 100k faces on the reference PC [H]** (87.5k [C] × 1.14 × 3): pose step 15 % ≈ 0.5–0.6 s, 100 %
≈ 3.2 s; Soft drag over 15,000 vertices ≈ 0.6 s; a 500-vertex W drag stays ≈ 15–30 ms with the wire off.

### E.3 Where one pose step goes [C] (`probe_scale_audit.py --only split`)

| Part of the step | 20k, 5 % (1,093 V) | 20k, 15 % (3,281 V) | 20k, 100 % (21,875 V) | 87.5k, 5 % (4,375 V) | 87.5k, 15 % (13,125 V) | 87.5k, 100 % (87,500 V) |
|---|---:|---:|---:|---:|---:|---:|
| **step total** (pointer_motion + update_viewport), ms | 10.2 | 43.3 | 235 | 67.9 | 177 | 922 |
| skin evaluation (LBS + `set_vertex_position` writes) | 14 % | 19 % | 21 % | 19 % | 22 % | 22 % |
| `RenderMesh._sync_geometry` | 79 % | 79 % | 77 % | 73 % | 77 % | 75 % |
|   of it: face rows (36 floats per face) → store | 26 % | 26 % | 24 % | 25 % | 26 % | 23 % |
|   of it: face normals, vertex normals, neighbourhood sets, positions + normals | 53 % | 53 % | 53 % | 48 % | 51 % | 52 % |
| GL transfer of the face data at draw (`glBufferSubData`) | < 1 % | < 1 % | < 1 % | < 1 % | < 1 % | < 1 % |
| bytes handed to the store per step | 0.21 MB | 0.60 MB | 3.7 MB | 0.80 MB | 2.3 MB | 14.7 MB |
| the same step with the wire overlay on, ms | 47.7 | 93.7 | 310 | 216 | 393 | 1,123 |
|   of it: wire segments of the whole mesh, ms | 31.6 | 44.6 | 40.7 | 150 | 179 | 153 |

Shares are of the step total. The five parts of `_sync_geometry` individually (first container host, 15 % rows): face
rows 27 % / 22 % of the step at 20k / 87.5k, face normals 20 % / 16 %, vertex normals 10 % / 9 %, positions + normals
14 % / 10 %, neighbourhood sets 6 % / 6 %. Reference PC for the 20k column **[RPC]**: 35 / 99 / 698 ms, 73 % and 77 %
in `_sync_geometry` at 5 % and 15 %.

Readings: (1) nothing in the step is a GPU cost — the "upload" is building Python lists; the driver call is 0.2–0.6 %.
(2) The largest single item is the face rows: copies of corner positions and corner normals per face, needed by the
fragment shader for polygon-flat and bilinear-quad-smooth shading (`gl_render_store.py:182, 249-276`). They are about
a third of the display cost and 86 % of the bytes. (3) The evaluation part is itself mostly not arithmetic:
`SkinSurface` spends its time in per-vertex method calls and tuple writes into a mesh copy.

### E.4 One-time costs and memory

See the table in §C.3. Two consequences that are behaviour, not just numbers: dialling a morph target in for the
first time, and entering a pose for the first time, each freezes the application for the time it takes to
`export_state` the base, `Mesh.from_state` a copy and build a second `RenderMesh` — 1.3–1.9 s at 20k and 6–7 s at
87.5k **[C]**, about three times that on the reference PC **[H]**.

### E.5 The same computations on packed arrays [C] (`probe_kernels.py`)

CPU side only. "production" = the code in `src/`; "flat Py" = the same normal patch in pure Python on int slots and
flat lists, without face rows; "NumPy" = NumPy 2.5.3 with runtime SIMD dispatch switched off (baseline instructions
only); "native C" = `kernels_native.c`, `gcc -O2 -march=core2` (only instructions the Q9550 has), single thread, via
`ctypes`. Every array kernel is checked against the production values first: skin and morph differ by exactly 0,
stencils by 3·10⁻¹⁶, normals by ≤ 3·10⁻¹⁴.

| ms per step, 87.5k mesh | region | production | flat Py | NumPy | native C |
|---|---:|---:|---:|---:|---:|
| **visible** (1-ring normals + buffer data) | 1 % (875 V) | 10.4 | 4.2 | 2.1 | 0.35 |
| | 5 % (4,375 V) | 49.8 | 15.6 | 7.6 | 0.47 |
| | 15 % (13,125 V) | 137 | 49.9 | 19.5 | 1.1 |
| | 100 % (87,500 V) | 799 | 262 | 51.5 | 4.6 |
| **skin** (LBS, evaluation only) | 5 % | 5.2 | — | 1.0 | 0.06 |
| | 15 % | 31.1 | — | 3.2 | 0.20 |
| | 100 % | 176 | — | 42.0 | 1.3 |
| **morph** (one weight step, one target) | 15 % | 9.7 | — | 0.63 | 0.06 |
| | 100 % | 96.1 | — | 6.2 | 0.57 |
| **SubD stencils**, level 1 → 350,000 derived V | all | 381 | — | 87.7 | 4.8 |
| all normals of the mesh from scratch | all | (in the 2.6–3.3 s `RenderMesh` build) | — | 53.8 | 3.7 |

| ms per step, 20k mesh | region | production | flat Py | NumPy | native C |
|---|---:|---:|---:|---:|---:|
| **visible** | 5 % (1,093 V) | 7.1 | 2.7 | 1.3 | 0.08 |
| | 15 % (3,281 V) | 19.0 | 7.3 | 3.4 | 0.18 |
| | 100 % (21,875 V) | 151 | 55.0 | 8.7 | 0.97 |
| **skin** | 15 % / 100 % | 5.6 / 35.7 | — | 0.85 / 6.1 | 0.05 / 0.30 |
| **morph** | 15 % / 100 % | 3.0 / 17.8 | — | 0.14 / 0.69 | 0.02 / 0.06 |
| **SubD stencils**, level 1 → 87,500 derived V | all | 82.7 | — | 17.7 | 0.73 |

Memory of the packed form (positions, corner arrays, adjacency, both normal sets, float32 mirrors): 3.0 MiB at 20k,
12.0 MiB at 87.5k.

Readings:
- **A whole-mesh deformation at 87.5k (morph + skin + normals) is about 1.07 s of CPU in production code, about 0.10 s
  in NumPy and about 6.5 ms in native C; a 15 % region 178 ms, 23 ms and 1.4 ms** — before any GPU is involved.
- "flat Py" shows how much is layout rather than language: dropping the ID dicts and the face rows alone gives 2.5–3×
  in pure Python. The rest needs vectorised or compiled kernels.
- NumPy gains 4–25× depending on the kernel (least on LBS and stencils as written here: generic `einsum` /
  `reduceat`, not tuned). Native code gains 30× on the smallest regions and 80–290× from a few thousand vertices up.
- Stencil evaluation of one SubD level (87.5k cage → 350k derived vertices): 381 ms → 88 ms → 4.8 ms.

**Reference-PC expectation [H].** Python parts × 3. For NumPy and native code no ratio has been measured on the Q9550;
assuming the same × 3: whole-mesh pose at 100k ≈ 0.35 s with NumPy and ≈ 22 ms with native kernels; a 15 % region
≈ 80 ms with NumPy and ≈ 5 ms native. **These are the figures the reference-PC run of §J replaces.**

### E.6 Topology operations and picking at 87.5k [C]

| Event (profiled, so 1.5–2× the unprofiled time) | Python-side work | Note |
|---|---:|---|
| Delete 1 face: journal → `MeshDeltaCommand`, `_patch_topology` | ≈ 8 ms | the rest of the 72 ms event is the software ID-pass render of the hover re-pick (10.3 ms GPU on the reference PC at this size **[RPC]**) |
| Undo of it: `apply_delta` | 15 ms | 7 ms of it is re-sorting the face table to ascending ID order (`mesh.py:2652-2659`, O(F log F) whenever an old ID returns) |
| Frame after either | < 1 ms sync | incremental patch |

The navigation probe's "op" column grows 3× from 20k to 87.5k (delete 16 → 45 ms, knife 31 → 105 ms). The profile
shows that growth is the ID pass on a software rasteriser, which the probe books under "op" — not Python work and not
a reference-PC cost. **Single-element topology edits are local at 87.5k.** Not local: anything under an active SubD
preview (global stencil rebuild: 1.0 s for a 21.9k-face cage, 3.7–5.2 s for an 87.5k-face cage **[C]**), and the start
of any symmetric gesture (§I.8).

---

## F. Scaling limits by cost centre

"Scales with" is what the measured cost follows. "At 100k" is the reading for the reference PC; [H] unless marked.

| Cost centre | Where | Bound | When | Scales with | Local? | Addressed so far | At 50k / 100k base faces |
|---|---|---|---|---|---|---|---|
| Core data access, topology traversal | `core/mesh.py` dict tables, `_vertex_edges` | CPU (interpreter) | per operation | touched elements | local | yes: adjacency index, local `collapse_edge`, journal | **not dominant** |
| Python object overhead / memory | `_VertexData` / `_EdgeData` / `_FaceData`, ID dicts, per-stage mesh copies | memory, GC | always | total mesh × number of stages | — | layers are packed; elements are not | 0.5 GB per object + 0.45 GB per active stage at 87.5k **[C]**; limits how many stages / objects fit |
| Morph evaluation | `morph_mix.MixSurface._recompute` | CPU (interpreter) | per weight step | points of the stepped target × active targets | local (sparse) | yes: sparse, drift-free | moderate alone (80–96 ms for 100 % at 87.5k **[C]**); always followed by the display cost |
| Skinning evaluation | `skinning.SkinSurface._recompute` | CPU (interpreter) | per pose step | points of the moved bones | local | index bone → points | 14–22 % of the pose step; ≈ 0.7 s per whole-mesh step |
| Soft Selection influence | `soft_selection/influence.py` | CPU | once per gesture, once per selection change with Soft on | euclidean: **all vertices**; geodesic: vertices within the radius | euclidean global, geodesic local | bounding-box reject | 93–105 ms per click at 87.5k **[C]** → ≈ 0.3 s; noticeable, not blocking |
| Symmetry | `symmetry.vertex_correspondence` (exact-position match of every vertex against its mirror image), mirrored writes | CPU | correspondence: at every symmetric gesture begin (`selection_helpers.resolve_symmetry` derives it twice), and wherever a caller asks; moves: per step | correspondence: **all vertices**; moves: moved vertices × 2 | correspondence **global**, by design without a cache ("pure function, no cache (AR-1)", `symmetry.py:212`) | no | one derivation 89 ms at 20k, 501 ms at 87.5k **[C]** → ≈ 1.7 s per derivation at 100k, two per gesture begin: **a pause of seconds at the start of every symmetric gesture** |
| SubD stencil evaluation | `SubdLevel.apply_local` / `apply_full` | CPU (interpreter) | per cage change | derived vertices touched (4× per level) | local below 12.5 % changed | yes | refused above 25k derived faces today; 381 ms per full update at 87.5k cage **[C]** |
| SubD topology / stencil build | `SubdSurface`, `topology_signature` | CPU | per topology edit under SubD | **whole cage** | **global** | derived mesh patched in place | 3.7–5.2 s per edit at 87.5k cage **[C]** → ≈ 11–16 s: a structural limit of the stencil design for dense cages |
| Stage first build | `rest_state` → `Mesh.from_state` → new `RenderMesh` | CPU, memory | first weight / pose step, target switch to a new surface | whole mesh | global | kept alive once built | 6–7 s **[C]** → ≈ 20 s freeze |
| Viewport geometry sync | `RenderMesh._sync_geometry`, `DerivedGeometry` | CPU (interpreter) | every step that moves anything | moved vertices + 1-ring | local | yes: 1-ring only, mirrors, merged ranges | **dominant: 73–79 % of every deformation step** |
| Normals, triangulation | `derived.py`; triangulation deferred to topology sync | CPU | as above / per topology sync | moved vertices | local | yes | part of the above (≈ 30 % of the step) |
| CPU → GPU transfer | `GLRenderStore.update`, `_flush_face_data` | sync; the GPU side is negligible | per step | bytes: 168–183 per moved vertex | local | merged ranges, direct `array` upload for face data | 14.7 MB per whole-mesh step at 87.5k; cost is list building, not the bus |
| Wire overlay | `Viewport._sync_edges`, `wireframe.edge_segments` | CPU | every geometry change while the wire is shown | **all edges** | **global** | no ("E39: accepted for B5a") | +117–180 ms **[C]** → ≈ +0.4–0.5 s per step: **dominant for every edit with the wire on** |
| Draw calls, rendering | one indexed draw + overlays | GPU | per frame | triangles, pixels | — | — | orbit at 175k triangles is fluid **[RPC, subjective 2026-10-17]**; draw 0.56 ms at 43,750 triangles **[RPC]**; shaded GPU time at 175k not measured (§J) |
| Picking, hover | GPU ID pass + `gpu_picking.py`; `PickCache` | GPU + CPU | per hover / click | ID pass: triangles; vertex / edge mode after a camera move: **all vertices + faces** | face mode local; vertex / edge **global after each camera move** | GPU picking (AD-022) — partly undone (§I.1) | 303–421 ms **[C]** → ≈ 0.9–1.3 s for the first hover after each orbit in vertex / edge mode at 87.5k |
| Box / Lasso | `gpu_elements_in_region` | CPU | per gesture | all vertices (+ all edges / faces) | global | depth oracle | 0.6–0.9 s at 87.5k **[C]** incl. software render |
| History, Undo / Redo | `MeshDeltaCommand`, `Mesh.apply_delta` | CPU, memory | per commit / undo | changed elements (+ a table re-sort when an old ID returns) | local | yes (AD-023 H1) | not dominant; no depth limit, a whole-mesh move stores every position twice |
| Selection change | `RenderMesh._sync_selection` | CPU | per hover / selection change | **all vertices** (a buffer the shader no longer reads) | global | no (known: drag_cost README "Next step", option 8) | 3.8 ms **[C]** → ≈ 11 ms per hover change at 87.5k |
| Load / save | OBJ → `Mesh` → `RenderMesh`; JSON | CPU | per load / save | whole mesh | global | — | load ≈ 14–18 s, save ≈ 3 s, 44 MiB file |
| UI | ImGui panels, HUD | CPU | per frame | panel content | — | — | 0.4–0.8 ms per frame **[RPC]**: not a factor |

**Evaluating a change against making it visible.** For the morph weight step: 2–3 ms to evaluate 3,281 points, then
≈ 20–34 ms to show them **[C]**. For the pose step: 14–22 % against 73–79 %. For a W drag: 12 % against 85 %. In every
case the display side is 3–10× the evaluation, and even a zero-cost deformation would leave three quarters of the
step — the AD-028 conclusion, now with its internal split.

---

## G. The central question

### G.1 Do the three layers exist?

- **A. Authoritative Core — exists, complete, and correctly bounded.** Topology, identity, provenance (origin
  interpolation in the primitives), History, morph offsets and skin weights as journaled point layers, symmetry and
  regions, serialization. Nothing derived writes into it (tests pin "never writes a scene mesh").
- **B. Evaluation layer — exists as a responsibility with a sound contract, but without its own representation.**
  `SurfaceChain` orders the stages; each stage is a pure, drift-free function of its inputs, driven by the journal,
  sparse where the change is sparse. Its *results*, however, are stored in the Core's own editing structure:
  `MixSurface.mesh` and `SkinSurface.mesh` are full `core.Mesh` objects whose topology is by contract identical to the
  base's ("same IDs and topology as its input"), re-created by replaying element records. The only thing these stages
  ever compute is one position per vertex.
- **C. Derived viewport representation — exists and is incremental, but is not compact.** `RenderMesh` has the right
  mechanisms (stable slot layout, spare capacity, journal-driven patches, CPU mirrors, GPU resource persistence). Its
  inputs arrive one `vertex_position(id)` call at a time; its derived data lives in dicts keyed by ID; its shading
  layout stores every vertex's position and normal once per adjacent face; the store keeps a further list copy.

So the boundaries are where the brief would put them; the seams (`MeshWatch`, the H7 provider contract
`sync(mesh, selection) → moved`, `RenderMesh.mark_vertices_dirty`) are narrow. What is incomplete is the *currency*
that crosses them: objects and ID sets instead of arrays and index ranges.

### G.2 The ceiling, stated precisely

Per moved vertex and frame the current design executes on the order of a few hundred interpreter-level operations in
at least five places (stage evaluation, journal touch, neighbourhood sets, normals, row packing), at ≈ 27–30 µs per
moved vertex in total on the reference PC **[RPC]**. A frame budget of 16.7 ms therefore buys ≈ 550–600 moved vertices,
33 ms about 1,200 — independent of mesh size. Micro-optimising inside this design has been done repeatedly (inlined
normals, batched uploads, mirrors) and each step gained tens of percent; a factor of 10–100, which regional deformation
on 100k needs, is not available that way. **That is the structural ceiling: per-vertex interpreter execution over
object graphs, multiplied by the number of copies a vertex has along the chain.**

It is not: the mesh data structure's topology model (no half-edge needed — unchanged from the 2026-10-27 audit), the
journal, the History, the GPU, or the bus.

### G.3 Options

| | What changes | Measured / expected gain | Preserved behaviour at risk | Reference-PC constraint |
|---|---|---|---|---|
| **O0 — fix what is simply global** (§I): wire rebuild per step, `PickCache.refresh` in the GPU pick path, the O(V) highlight buffer, the symmetry correspondence per gesture | four local fixes in `src/viewport` / `src/mirai` (the correspondence can follow the journal instead of being re-derived; its "no cache" rule AR-1 is a documented decision and needs revisiting, not just code) | removes the largest costs of everyday modeling at 20k *today*; does nothing for regional deformation | none (covered by existing GL tests; the pick fix needs the n-gon occlusion case kept) | none |
| **O1 — evaluated surfaces stop being mesh copies** | mix and skin produce a position table over the base's topology (a read-only view with the `Mesh` query API) instead of `Mesh.from_state` + replayed topology | removes ≈ 0.45–0.49 GB and 6–7 s per stage at 87.5k **[C]**, the per-stage topology replay, and one journal hop; per-step gain modest | the H7 consumers that read the surface mesh (picker on the mix, overlays, wire, SubD input) — all read-only and already test-pinned | none; can be pure Python |
| **O2 — the render layout stops duplicating vertex data per face** | face rows hold the face's vertex *slots* (topology-only); the shader fetches positions / normals from the vertex buffers bound as buffer textures | removes "face rows" (23–26 % of every step **[C]**, 86 % of the bytes); a deformation then uploads 24 bytes per vertex instead of ≈ 176 | the look of Flat and bilinear Smooth (an Artist KEEP) — same math, different fetch; must be compared pixel-wise | dependent `texelFetch` on the 9800 GTX: buffer textures and `gl_PrimitiveID` already work there **[RPC]**; the fragment cost needs a prototype on that card (not part of §J) |
| **O3 — packed arrays as the currency (NumPy)** | a slot-indexed array mirror of positions and topology kept in step from the journal (the pattern `LayerSlots` + `PackedValues` already use in the Core); stages and `RenderMesh` compute on arrays; ID sets become index arrays | 4–25× per kernel **[C]** (§E.5); with O1 + O2 the whole chain: ≈ 10× on a whole-mesh step | results are bit-identical for skin / morph / stencils, 10⁻¹⁴ for normals — tests comparing normals exactly need a tolerance or a fixed summation order | **NumPy becomes a dependency.** Only a pre-x86-64-v2 build imports on the Q9550 (2.2.6 under Python 3.12 **[RPC, import only]**); Python 3.14 has no such wheel. Needs Manu's decision (REFERENCE_HARDWARE §4) and a timing run (§J) |
| **O4 — native kernels behind the same arrays** | 5 small C functions (normals, LBS, morph, stencils, patch) | 30–290×, above 100× for regions of thousands of vertices **[C]**; whole-mesh deformation at 100k in the low tens of ms **[H]** | none beyond O3 (same arithmetic, same order → bit-identical in the prototype) | a compiled binary must be built for and shipped to Windows; no compiler is known on the reference PC. A tooling decision, only worth taking if O3 measures too slow |
| **O5 — GPU evaluation** (skin / morph in the vertex shader) | positions never return to the CPU | removes evaluation and upload for the *final* stage | **high**: SubD after skin, the wire, overlays, Flat / Smooth face data and picking on the mix all read evaluated positions on the CPU (AD-028 X-5 says the same) | GL 3.3 can do it; but it bypasses exactly the combinations that are Mirai's identity. Only as a late, optional path for pure pose playback |
| **O6 — rewrite the Core** (array-of-structs / half-edge / native) | everything | none measured — the Core is not on the hot path | **very high**: 6,900 tests, the Knife oracle, every tool | — |

O0–O2 are independent of each other and of O3; O3 is what makes O1 and O2 pay fully; O4 is contingent on a
measurement; O5 and O6 are not recommended.

### G.4 What the reference hardware can support

- **GPU.** Draw is not the limit at 100k base faces: 0.56 ms per frame at 43,750 triangles **[RPC]**, fluid orbit at
  175,000 triangles **[RPC, subjective]**. The ID pass took 10.3 ms at 175,000 triangles **[RPC]** — 9× the 20k value
  for 4× the geometry, so geometry throughput is finite and near: 2–3 passes per frame (shaded, wire, ID) at 100k faces
  put the frame around 15–30 ms **[H]**, i.e. 30–60 Hz navigation. SubD on top (4× the triangles per level) does not
  fit **[H]**. Not measured: the shaded pass's GPU time at 175k triangles, and how fast the driver takes megabytes of
  `glBufferSubData` per frame (§J: the navigation probe's `gpu` column, and the scale probe's `face-data
  glBufferSubData` row at 100 %, which is that transfer for ≈ 12.6 MB).
- **CPU.** One 2.83 GHz core without AVX / FMA / SSE4.2. The native prototype was compiled for exactly that
  instruction set and needs 3–5.5 ms for all 1-ring normals of 87,500 vertices and about 1 ms to skin them **[C]**; how much
  slower the Q9550 runs that code is not measured. Three more cores are unused by the application and are not needed
  for the target.
- **Memory.** 8 GB. Today ≈ 0.5 GB per dense object and ≈ 0.45 GB per active stage **[C]**; as arrays ≈ 12 MiB per
  object and ≈ 2 MiB per stage.
- **Blender on the same machine** shows the target is not unreasonable; it computes on contiguous arrays in compiled
  code. That is a statement about where the time goes, not a recommendation to adopt its architecture (not verified
  against its source here).

---

## H. Recommendation and decisions

**Recommendation: evolve, do not rewrite.** Keep the Core and every editing semantic exactly as they are. Change what
flows out of it.

**Proposed order (plan only — each step is its own work package with its own gate; nothing here is implemented):**

1. **O0 now** (Production fixes, size S–M each): incremental or deferred wire, no whole-mesh `PickCache`
   refresh on the GPU hover path, drop the dead highlight upload, a journal-following symmetry correspondence.
   *Gate:* the existing GL test files; the wire-on rows of `probe_scale_audit.py` equal to the wire-off rows; `[GPU]
   vertex / edge first pick` of `probe_picking_app.py` at 20k back to the documented 16 / 21 ms in a container.
2. **Reference-PC measurements** (§J) — before any design: the kernel probe under Python 3.12 + NumPy 2.2.6, and the
   scale probe at 20k and 87.5k. They replace every [H] in §E.5 and §G.4.
3. **Decision D1 (Manu):** may NumPy (pinned to a build that runs on the Q9550, under Python 3.12) become a
   production dependency? Without it only O0–O2 remain, worth roughly 2–3× on deformation steps **[H, from "flat Py"]**.
4. **O2 then O1** — both are representation changes behind existing contracts and existing oracles; O2 first because
   it is the single largest share of every step and is independent of D1.
5. **O3** — the array mirror and array kernels, stage by stage (normals → skin → morph → SubD stencils), each
   accepted against its existing definition test. *Gate per stage:* bit-identical (or stated tolerance) against the
   oracle; the pose-step and weight-step rows on the reference PC.
6. **Decision D2:** O4 only if step 5 leaves the agreed bar unmet on the reference PC.

**Decisions needed from Manu**

- **D1** NumPy as a dependency (above).
- **D3** The bar for "fluid" at 100k: which operation, which region size? A whole-mesh pose at 100k and a jaw-sized
  region are two orders of magnitude apart; the first needs O4, the second probably not **[H]**.
- **D4** Is SubD on a 100k-face cage a goal on this PC, or is "SubD on a low cage, dense base without SubD" the
  intended split? The stencil design rebuilds globally on every topology edit (§F) and the GPU load does not fit (§G.4).
- **D5** Should the 87.5k asset be committed (5 MB OBJ) so dense measurements are reproducible, and should
  `MAX_DERIVED_FACES` be measured on the reference PC instead of carried over from the Lab?
- **D6** (with review) May the symmetry correspondence be kept current from the change journal instead of being
  re-derived per call? "No cache" (AR-1) was a deliberate rule for correctness; at 20k+ it costs a visible pause per
  symmetric gesture (§I.8).

**What this audit does not claim.** That NumPy or native kernels reach a given frame time on the Q9550 (not measured
there); that O2's shader is as fast on the 9800 GTX (not measured); that symmetric operations scale like their
non-symmetric counterparts at 20k+ (not measured); that 100k faces with all stages active fit a comfortable budget.

---

## I. Findings outside the central question (current defects, each small)

1. **Vertex / edge hover after a camera move re-projects the whole mesh again.** `gpu_pick_component`
   (`src/mirai/viewport/gpu_picking.py:46-47`) calls `PickCache.refresh` before the vertex and edge passes so that
   `vertex_occluded` / `edge_point_occluded` can run their CPU ray test; after any camera change that is a full
   re-projection (`picking_cache.py:124`). Same probe, vertex / edge first pick: 16 / 21 ms **[C]** on 2026-10-21 →
   77 / 104 ms **[C]** now at 20k, 421 / 303 ms at 87.5k (face mode unchanged: 11 → 11.5 ms, so the two containers
   are comparable); the reference PC measured 6.9 / 8.2 ms before **[RPC]**. Git cannot date the change (the file
   enters history in a bulk commit, `ac4651e`). The occlusion test needs the faces near a handful of candidates,
   not the whole mesh.
   **Fixed 2026-11-11 (O0):** the ray test visits only the faces the face pass drew around the candidate; the
   own-face-in-front (Ngon) case keeps the whole-mesh test (AD-022 §11). Container, 20k, p50: 91 / 73 ms before →
   12–17 / 17–26 ms after **[C]**.
2. **The wire overlay is rebuilt for all edges on every geometry change** (`viewport.py:919`, `wireframe.py:16`):
   +26–45 ms at 20k and +117–180 ms at 87.5k per step **[C]**, for a 1-vertex move as for a pose step (a 500-vertex W
   drag at 87.5k: 7.6 ms with the wire off, 144 ms with it on). Not measured on the reference PC; ≈ +75–130 ms at
   20k **[H]**. The GPU picker already keeps an edge index buffer over the mesh's position buffer
   (`RenderMesh.edge_indices`) — the wire could draw from that with no per-step work.
   **Fixed 2026-11-11 (O0):** the wire is drawn from the `RenderMesh` VertexList through those edge slots
   (`GLLineOverlay.draw_mesh_wire`, AD-018 addendum 2026-11-11); `edge_segments` stays only for headless stores.
   `probe_scale_audit.py --only split` **[C]**, pose-step p50, wire off / on: 20k 15 % 34.6 / 80.0 ms before →
   26.4 / 29.7 ms after, 20k 100 % 236 / 221 → 227 / 218 ms (both runs noisy at 100 %); 87.5k 15 % 177 / 393 ms
   (§E.3) → 127 / 140 ms; "wire segments" 36 / 28 / 179 ms → 0.
3. **`RenderMesh._sync_selection` builds and uploads a V-sized `highlight_flags` buffer on every hover / selection
   change** (`render_mesh.py:634, 1084`) although the fragment shader no longer reads it (comment at
   `gl_render_store.py:71-74`): 96 KB per hover change at 20k, 385 KB at 87.5k. Known and open since 2026-10-17
   (drag_cost README "Next step", option 8).
   **Fixed 2026-11-11 (O0):** the `highlight_flags` pipeline is removed (AD-018 follow-up, done); a selection or
   hover change uploads nothing to the mesh buffers. Hover change through `Viewport.sync` at 20k **[C]**: 0.78–0.82 ms
   and 87.5 KB before → 0.01 ms and 0 bytes after.
4. **Two probes had bit-rotted.** `probe_picking_app.py` and the `direct` scenario of `probe_navigation_gl.py` used
   `Application._edit_camera` and `Application._paint_at`, which no longer exist (now `app._objects.edit_camera`,
   `app._pointer_tools.paint_at`). Fixed in this commit (probe code only); both run again.
5. **The dense asset is gone.** `examples/meshes/gollum.obj` == `gollum_20k.obj` (§D). `probe_scale_audit.py
   --make-dense` regenerates an 87.5k mesh locally (not committed, D5).
   **Settled 2026-11-11 (D5):** committed as `experiments/drag_cost/fixtures/gollum_87k.obj` with its provenance;
   `--verify-dense` regenerates it byte for byte.
6. **Undo of a deletion re-sorts a whole element table** (`mesh.py:2652-2659`): about 7 ms at 87.5k **[C]**, harmless
   today, listed because it is the one O(mesh) step left in the Core's undo path.
7. **A temporary local test is in git and fails:** `tests/test_scene_menu_local_tmp.py` ("wird gelöscht, nicht
   committen"), §B. It makes `pytest tests` red. Not removed here — it is Manu's file.
8. **The symmetry correspondence is derived for the whole mesh on every call** (`symmetry.py:118`; a dict of every
   position, then one mirror lookup per vertex): 2.1 ms at 928 V, 89 ms at 21,875 V, 501 ms at 87,500 V **[C]**.
   `resolve_symmetry` (`interaction/tools/selection_helpers.py:63`) triggers it twice per symmetric transform begin.
   That fits the once-per-gesture "Symmetrie-Befund" of 17 ms the reference PC recorded on the body mesh on
   2026-10-15 **[RPC]** (2 × 2.1 ms **[C]** × 3 ≈ 13 ms). Scaled the same way: ≈ 0.5 s at 20k and ≈ 3.4 s at 100k per
   symmetric gesture begin on the reference PC **[H]**. Live Symmetry is the one preserved capability whose cost on
   the *editing* side, before any display, grows with mesh size.

---

## J. Measurements needed on the reference PC

Each prints plain ASCII; paste the whole output. None changes anything.

```
python experiments\drag_cost\probe_scale_audit.py
```
Pose-step split (wire off / on) at 15 % and 100 % on `gollum_20k` and the generated 87.5k mesh, then the one-time costs
and memory. It writes the dense mesh on first use. Slow on the dense mesh (estimated 10–15 minutes in total **[H]**);
add `--assets examples\meshes\gollum_20k.obj` for the short form.

```
python experiments\drag_cost\probe_picking_app.py
```
Confirms or refutes finding I.1 on the reference PC (compare "vertex first pick" under `[GPU]` with 6.94 ms of
2026-10-21).

```
py -3.12 -m pip install "numpy<2.3"
py -3.12 experiments\drag_cost\probe_kernels.py --assets examples\meshes\gollum_20k.obj dense
```
The NumPy columns on the Q9550 — the number decision D1 depends on. Under Python 3.14 the probe reports "NumPy not
usable" and prints the production and pure-Python columns only. The native column appears only if `gcc` / `clang` is on
PATH (not required).

```
python experiments\drag_cost\probe_navigation_gl.py --assets experiments\drag_cost\_generated\gollum_87k.obj --scenarios orbit orbit_wire plain_w
```
The `gpu` column is the real GPU time of the shaded pass at 175,000 triangles (§G.4).

---

## K. What was not measured or verified

- Nothing was measured on the reference PC by this audit.
- Symmetric Soft Selection and symmetric drags at 20k+ through the application (no symmetric dense asset in the
  repository); only the correspondence function itself was timed (§I.8).
- GPU time of the shaded pass and upload throughput on the 9800 GTX at 100k.
- NumPy 2.2.x timings (the container has 2.5.3; its runtime dispatch was switched off to stay near the baseline).
- Topology edits with a morph target dialled in at 87.5k (`probe_morph_gl.py --only-topology` exists; not run dense).
- A W drag with a morph target dialled in (the edit mesh's and the mix surface's `RenderMesh` are then both synced
  per step — the code path is in §C.2 item 3; its cost was not measured separately).
- Multi-object scenes, textures, the ZBrush bridge, the Morph Lab, the Knife oracle.
- Whether O2's shader form reproduces the current image exactly.

---

## L. Raw outputs

[`experiments/drag_cost/RESULTS_SCALE_AUDIT_CONTAINER_2026-11-10.md`](../../../experiments/drag_cost/RESULTS_SCALE_AUDIT_CONTAINER_2026-11-10.md)
holds the commands and the complete outputs of the split, chain, kernel, navigation and picking probes as run for
this audit. The event profiles quoted in §E.6 and §I.1 (cProfile of single events at 87.5k) came from scratch scripts
that are not kept; they are re-runnable from the description there (`Application.key_press` / `pointer_motion` under
`cProfile` after `probe_morph_gl.build_app`).


---

## Addendum — Reference-PC measurements (Manu, 2026-11-10)

The requested runs from §J have now been supplied and recorded. The original first-pass findings above, including the wording in §K (“Nothing was measured on the reference PC by this audit”), describe the state when this audit was delivered; they are intentionally retained as historical record. This addendum records the later reference-PC evidence without rewriting that first pass.

Full command output:
[`experiments/drag_cost/RESULTS_SCALE_AUDIT_REFERENCE_PC_2026-11-10.md`](../../../experiments/drag_cost/RESULTS_SCALE_AUDIT_REFERENCE_PC_2026-11-10.md).

### Results that replace the open measurements in §J

- `probe_scale_audit.py`: Q9550 / 9800 GTX measurements completed at 20k and 87.5k. At 87.5k, a 15 % pose step is 399.20 ms p50 with wire off; `RenderMesh._sync_geometry` accounts for 321.59 ms (80.6 %). With wire on the step is 728.70 ms, including 329.02 ms for rebuilding all wire segments. Whole-mesh pose is 2,815.70 ms without wire and 3,142.96 ms with wire.
- One-time costs on 87.5k: load + first frame 11.665 s; first mix surface 9.533 s; first skin surface 11.088 s. The SubD preview is still refused by the 25,000-derived-face guard.
- `probe_picking_app.py`: GPU first-pick p50 is 167.10 ms for vertices and 164.84 ms for edges; face first-pick is 3.39 ms. The navigation profile also shows full `PickCache.refresh` / projection / bounding-box work during zoom and first-hover profiling.
- NumPy 2.2.6 installs and runs under Python 3.12.10 on the Q9550. At 87.5k / 15 %, CPU-only kernel timings are 30.711 ms (visible-data preparation), 11.723 ms (skin), and 0.891 ms (one target morph). Skin and morph match production exactly in the probe; normal and SubD differences are within the reported floating-point tolerances. These are isolated kernels, not an integrated application-frame measurement.
- `probe_navigation_gl.py`: 87.5k orbit is 1.73 ms p50 (GPU timer 0.76 ms); orbit with wire is 6.25 ms p50 (GPU timer 4.98 ms). The 500-vertex W move is 17.42 ms p50 before its separately reported 6.82 ms draw.
- Native C was not measured (no compiler on PATH). No pytest output was included in the supplied run, so test-suite status remains unreported here.

### Consequence for the recommendation

The reference-PC results confirm the location of the deformation and wireframe costs, and establish that NumPy 2.2.6 can execute the isolated packed-array kernels on the target CPU under Python 3.12.10. They strengthen the case for the staged O0–O3 direction; they do **not** yet prove end-to-end application performance after integration or O2 shader equivalence. O4 remains conditional on later integrated measurements.

The raw run does not include a repository commit SHA or working-tree status. Record those on the next baseline run so future comparisons can identify the exact source revision.

## Addendum — O0 on the reference PC (Manu, 2026-11-11)

§I.1–§I.3 were fixed in `5a739c0`, `d1b370a`, `57f3177` (status lines in §I). Manu's run on the Q9550 / 9800 GTX
after those commits, raw output and comparison table:
[`experiments/drag_cost/RESULTS_O0_REFERENCE_PC_2026-11-11.md`](../../../experiments/drag_cost/RESULTS_O0_REFERENCE_PC_2026-11-11.md).

- **Gate §H step 1, GL tests:** `test_gl_gpu_picking.py` + `test_gl_line_overlay.py` 39 passed on this driver.
- **Gate, wire:** wire-on rows equal the wire-off rows **[RPC]**: 20k 15 % 93.99 / 95.18 ms (before 96.37 / 181.77),
  20k 100 % 639.83 / 644.37 (681.28 / 762.83), 87.5k 15 % 391.73 / 398.76 (399.20 / 728.70), 87.5k 100 %
  2,737.65 / 2,742.38 (2,815.70 / 3,142.96); "wire segments" 0 ms in every row; the GPU line draw adds 1.7–3 ms to
  `draw + glFinish`.
- **Gate, picking:** `[GPU]` vertex / edge first pick **[RPC]** 167.10 / 164.84 → **11.00 / 12.62 ms**: below one frame
  (AD-022 §9 abort criterion 1), but above the 6.94 / 8.23 ms of 2026-10-21. Face first pick 3.30 ms (unchanged).
- **Open, not O0:** `[GPU]` vertex / edge hover is 6.49 / 7.65 ms (6.25 / 6.97 before O0, 2.15 / 2.72 on 2026-10-21;
  the maxima fell from 52 / 74 to 10 / 13 ms). The rise is older than O0 and coincides with the CPU occlusion rule of
  the Ngon fix (2026-10-22); its split on this PC (ID-buffer reads vs. ray tests) is not measured.
  *Follow-up 2026-11-11:* profiled in the container: ~70 % of the hover's CPU was the per-candidate camera basis in
  `project_to_screen` (~200 candidates per vertex hover); plus one ID read per tested candidate. Fixed (AD-022 §11
  "Hover split"): hover vertex / edge 1.1 / 2.2 → 0.5–0.7 / 0.7–1.05 ms **[C]**, 2 reads per hover; the probe now
  prints the read share for the reference-PC run. Reference PC **[RPC]**: hover 6.49 / 7.65 → 4.46 / 4.17 ms (reads
  ~0.95 ms of it), first pick 8.58 / 9.31 ms; both well inside one frame. Not pursued further now (see AD-022 §11).

## Decisions (Manu, 2026-11-11)

Recorded as given; they settle §H "Decisions needed from Manu". The plan order of §H stays: O2, then O1, then O3; D6
separate from O1/O2.

- **D1 — NumPy as a production dependency: YES**, for O3. Initially pinned `numpy==2.2.6`; Python 3.12.10 is the
  verified runtime on the reference PC; keep compatibility with the Q9550 (no x86-64-v2 requirement). Do not pull NumPy
  into O1/O2 prematurely — it becomes relevant for O3 (so it enters `requirements.txt` with the first O3 stage, not
  before). Verify the actual production import and execution on the reference PC.
- **D2** — unchanged: O4 only if O3 leaves the D3 bar unmet on the reference PC.
- **D3 — "fluid" at ~100k base faces.** Minimum acceptance **p95 ≤ 33.3 ms** (30 FPS); preferred target **p95 ≤ 16.7 ms**
  (60 FPS). Primary acceptance scenario: ~100k base faces, a jaw-sized deformation region of ~15 % of the vertices,
  Morph and Skin active together, the complete interaction frame (evaluation, viewport synchronisation, overlays,
  drawing), measured with the wireframe ON and OFF. A whole-mesh deformation (100 %) remains a stress benchmark on the
  reference PC, not a mandatory 60 FPS requirement.
- **D4 — SubD on a 100k-face cage: NO for the reference PC.** Intended workflow: SubD preview on a lower-resolution
  working cage; dense base meshes are edited without live SubD. Higher-density SubD on future hardware is not
  permanently ruled out.
- **D5 — Reproducibility and `MAX_DERIVED_FACES`: YES.** The generated 87.5k benchmark mesh is committed under
  `experiments/drag_cost/` as a reproducible test fixture (not a production example asset), with its provenance and
  generation method (`experiments/drag_cost/fixtures/README.md`). `MAX_DERIVED_FACES` is measured on the actual
  reference PC; the limit is not raised on assumptions. The final threshold assessment comes **after O2**, since the
  viewport representation and shader path will have changed.
- **D6 — journal-maintained symmetry correspondence: YES, with strict conditions.** Investigate and implement a
  transient, journal-maintained derived correspondence cache above the Core:
  1. The Core remains authoritative. No symmetry correspondence is persisted or serialized.
  2. The existing cache-free `vertex_correspondence()` remains the reference implementation and test oracle.
  3. The cache must correctly handle position changes, topology changes, seam changes, symmetry-definition changes,
     Undo/Redo and scene load/replacement.
  4. Unknown or unsupported change events invalidate the cache and trigger a fresh derivation. Never use potentially
     stale correspondence.
  5. Randomized equivalence tests compare the cached result against the fresh reference implementation, including
     ambiguous and unpaired vertices.
  6. The cache stays outside `src/core/mesh.py`.

  This is an explicit, reviewed evolution of AR-1/INV-3, not permission to introduce arbitrary caches. It needs its own
  design review and acceptance gate, separate from O1/O2. Done already, cache-free (`733ab55`): the duplicate derivation
  in `resolve_symmetry()` and `MoveTool.begin()` (both derived twice per gesture begin; now once, passed to
  `mirrored_selection(correspondence=...)`), 122–153 → 44–82 ms at 20k **[C]**.

## Addendum — O2 in the container (2026-11-11)

§H step 4, first half (O2; Manu's decisions above: O2 before O1, no NumPy). Implemented in `58f7052`, decision record
[AD-018 addendum 2026-11-11](../../architecture/AD-018-PRODUCTION-DRAW-BINDING.md); the acceptance probe of D3 came first
(`23faef5`, `experiments/drag_cost/probe_d3_acceptance.py`). Raw outputs and the reference-PC commands:
[`experiments/drag_cost/RESULTS_O2_CONTAINER_2026-11-11.md`](../../../experiments/drag_cost/RESULTS_O2_CONTAINER_2026-11-11.md).

- **What changed.** The 36-float face row of §E.3 is gone. Per face: one vec4 (Newell normal, corner count) — the only
  face data a deformation writes — and two vec4 of topology (corner slots, region tint). The fragment shader reads the
  corners' positions and normals from the VertexList's own vertex buffers (bound as buffer textures). No NumPy, no
  Core change, no change to evaluation stages.
- **Gate: shading pixel-identical to the old path [C, test-verified].** `tests/test_gl_face_data_layout.py` (16 scenes
  against the pre-O2 shader frozen as an oracle; byte-identical) and a one-time cross-check against the `bc0f0b2`
  tree (16 scenes on `head_basemesh` / `gollum_20k`, deformed; byte-identical).
- **Gate: GL tests [C].** `tests/test_gl_*.py` in its own process: 165 passed. `tests/`: 6,907 passed, 1 failed (the
  pre-existing §I.7 file), 8 skipped (GL modules in the combined run).
- **Gate: bytes and time per step [C], 87.5k, 15 % region:**

| | before | after |
|---|---:|---:|
| bytes to the GL store per deformation frame | 2,304,924 (176 per region vertex) | **556,940 (42)** |
| of it face data | 1,969,344 | **221,360** |
| face data → store, p50 ms (D3 probe, two pairs) | 36–49 | **10–14** |
| D3 frame, pose, wire off / on, p50 (pair 2) | 225.9 / 269.1 | **198.9 / 234.6** |
| D3 frame, pose, wire off / on, p95 (pair 2) | 289.8 / 357.9 | **245.1 / 271.3** |
| D3 frame, weight, wire off / on, p50 (pair 2) | 264.5 / 317.1 | **261.7 / 298.3** |
| pose-step split (skin only, §E.3 scenario), step p50, wire off | 189.4 | **137.5** |
| face data share of that step | 24.6 % | **6.6 %** |
| draw, old vs new shader alternately in one process (llvmpipe), Smooth / Flat | 49.6 / 37.3 | 49.4 / 38.0 |

- **D3 verdict [C]: OVER** (33.3 ms p95) in every row, before and after — as §G.2 predicted for O2 alone. What remains
  per frame is per-vertex Python work O2 does not touch (stage evaluation, face and vertex normals, neighbourhood sets,
  position / normal mirrors: ≈ 130 of the ≈ 150 ms tick in the pose row) and, in the container, the software draw. The
  next steps stay O1, then O3 (§H).
- **Open, reference PC:** the D3 probe before / after, the GL tests (pixel identity on that driver) and the shaded
  pass's GPU time with the new texel fetches (a Smooth-quad fragment makes 27 fetches, 24 of them single floats,
  instead of 10). D5's `MAX_DERIVED_FACES` assessment, due "after O2", is not part of this step.

## Addendum — O2 on the reference PC (Manu, 2026-11-11)

Raw output and comparison:
[`experiments/drag_cost/RESULTS_O2_REFERENCE_PC_2026-11-11.md`](../../../experiments/drag_cost/RESULTS_O2_REFERENCE_PC_2026-11-11.md).

- **Pixel identity on the 9800 GTX driver [RPC]:** the GL tests pass (165), among them
  `tests/test_gl_face_data_layout.py` (production path against the frozen pre-O2 shader, byte-identical).
- **Deformation step [RPC]** (the §E.3 split, 87.5k, 15 %): 391.73 → **299.17 ms** p50 wire off, 398.76 → **294.02 ms**
  wire on; face data → store 106.39 → **22.34 ms**, bytes 2.30 → **0.56 MB**; every other part unchanged.
- **GPU cost of the new fetches [RPC]:** shaded pass 0.76 → **2.76 ms** GPU timer, orbit frame 1.73 → 4.08 ms p50 (0 of
  40 frames over 16.7 ms), 1024×768. The driver has no `GL_ARB_texture_buffer_object_rgb32`, so `RGB32F` buffer
  textures are not a lever on this PC.
- **D3 [RPC]** (panels off: Python 3.14.2 has no `imgui-bundle`), p50 (p95), wire off: pose 426.37 (433.35) →
  **352.98 (360.14)**, weight 506.38 (516.11) → **431.05 (440.80)**; wire on 441.46 → **366.33**, 514.13 → **424.99**.
  Still 10–13× over the bar. The tick fell by ≈ 89 ms (face data 107.58 → 22.34), **`on_draw` rose by ≈ 15 ms** (pose
  34.90 → 50.11): its CPU parts are small (viewport render 3.6, gizmo 1.0, HUD 1.1, triad 0.4 ms), the rest is the GPU
  wait in `glFinish` — ≈ 44 ms after O2 against ≈ 28 ms before. GPU timers (round 1): the mesh draw costs 43 ms with
  face data, 41 ms when the buffer textures read a copy no update touches, 9 ms without face data — so not the
  overlap of updates and buffer textures, but the face-data fetches, which cost only 2 ms in an orbit. Open O2 item:
  round 2 (`--interactions still`, `--face-upload orphan`) tells whether this driver makes buffer-texture fetches slow
  in frames that update a buffer texture, or whether the posed view itself is that expensive.
- **HUD during a weight drag [RPC]: 24.5 ms per frame** (pose: 1.1 ms), gizmo / bones 6.9 ms (pose: 1.0) — the weight
  read-out changes every frame. Size-independent, outside O2.

