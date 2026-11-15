# Surface Slide — Production Readiness Audit (2026-11-14)

**Status:** audit, English with a German summary. No Production change. **Phase 0 closed 2026-11-14: Manu's
decisions are recorded in §5.1**; **Phase 1 (pure core `src/mirai/surface_slide/`) done 2026-11-15, gate G1 green:
implementation note §13.1; Phase 2 (plan, region capture, symmetry) done 2026-11-15, gate G2 green: §13.3; Phase 3
(gesture on hold `J`, E6 answered 2026-11-15) done 2026-11-15, gate G3 green: §13.5.** It reviews the research
[SURFACE_SLIDE_ALGORITHM_RESEARCH_2026-11-13.md](SURFACE_SLIDE_ALGORITHM_RESEARCH_2026-11-13.md) (commit `ec3816d`) and
its prototype [`experiments/surface_slide/`](../../experiments/surface_slide/README.md) against the current Production
code at `main` @ `6282cd5`. New measurements come from six small probes in
[`experiments/surface_slide/audit_2026-11-14/`](../../experiments/surface_slide/audit_2026-11-14/README.md); they import the
prototype unchanged and touch nothing in `src/`.

**Markers.** **[M]** measured (prototype report or this audit's probes; container unless stated). **[V]** verified by
reading the code. **[T]** theory, estimate or assumption, not measured. **[O]** Artist decision for Manu. `h` = mean edge
length of the reference mesh.

**Classification of open problems.** **MR** must be resolved before implementation · **DI** can be resolved during
implementation · **V1L** acceptable V1 limitation · **AD** explicit Artist decision required.

---

## Kurzfassung für Manu (Deutsch)

**Urteil:** Der Algorithmus (Punkte gleiten auf einer festgehaltenen Kopie der Fläche, jeder Punkt an seiner Stelle
verankert, mit Tempolimit) ist für eine erste Version **ausreichend geprüft**. Er springt nicht zwischen Ober- und
Unterlippe, bleibt exakt auf der Fläche, Soft Selection und Symmetrie funktionieren, und das Muster passt zu Vertex
Slide und Loop Slide (ein Undo-Schritt, Esc stellt exakt wieder her). **Bauen sollte man ihn erst, wenn ein paar
Grundsatzfragen beantwortet sind**, und mit drei technischen Änderungen gegenüber dem Prototyp:

1. **Die Fläche, auf der gleitet wird, muss die gezeichnete sein.** Mirai zeichnet Vierecke anders in Dreiecke als der
   Prototyp. Und: die gezeichnete Fläche selbst ist **nicht spiegelsymmetrisch** (bei Gollum bei 766 von 809
   Spiegelpaaren; bis zu einer halben Kantenlänge Abstand, im Mittel 2 %). Lösung ohne neue Triangulierung: auf der
   gezeichneten Fläche der aktiven Hälfte gleiten, die andere Hälfte exakt spiegeln (wie heute bei Vertex Slide).
2. **Die Kopie der Fläche darf nicht das ganze Mesh umfassen.** Auf dem Referenz-PC würde das beim Drücken bei 20k
   Punkten etwa 0,6 s und bei 87k etwa 3 s kosten (geschätzt). Kopiert wird nur die Umgebung der Auswahl.
3. **Die Richtung, in die jeder Punkt gezogen wird**, sollte ohne den „Baum“ des Prototyps berechnet werden: der Baum
   erzeugt an Nase, Lid und Lippe Sprünge von 30–70° zwischen Nachbarpunkten. Die einfachere Variante ist genauso
   formtreu und beim Start 50–90× schneller; sie hat einen Sonderfall, der beim Bauen geprüft wird.

**Was Du entscheiden musst** (je eine Zeile genügt, Details §5):

- **E1** Fläche pro Zug neu (einfach; bei vielen Zügen auf groben, runden Stellen sinkt die Form minimal ein) oder
  festgehalten (konsistenter, aufwendiger)? Kanten-Fläche oder geglättet (glatter, rundet harte Kanten)?
  *Vorschlag: pro Zug, Kanten-Fläche.*
- **E2** Bei eingeblendetem Morph (z. B. 50 % Mund auf): gleiten auf der Ruheform oder auf der sichtbaren Form?
  *Vorschlag: Ruheform.*
- **E3** Über die Spiegelebene hinweg gleiten erlauben, oder kurz vor der Mitte anhalten (wie Vertex Slide bei 98 %)?
  *Vorschlag: anhalten.*
- **E4** Erste Version ohne „Punkt bleibt exakt unter der Maus“? Auf schrägen Flächen bleibt der Punkt zurück (heute
  0–92 % des Wegs, gemessen). *Vorschlag: ja, im Praxistest prüfen.*
- **E5** Punkte am offenen Rand (Augen-, Mundöffnung): am Rand entlang gleiten, oder stehen bleiben?
  *Vorschlag: entlang gleiten.*
- **E6** Welche Taste / welcher Modus? (Neben `G` = Vertex Slide; Tasten trägst nur Du in `keymap.json` ein.)
- **E7** Wenn ein Punkt beim Loslassen noch hinterherläuft: so übernehmen, wie er zu sehen ist? *Vorschlag: ja.*

Nicht in der ersten Version (Vorschlag): geglättete Fläche, festgehaltene Fläche, Gleiten auf einem anderen Objekt
(Retopo), Gleiten auf der SubD-Fläche, eine Formkorrektur für große Wege, Punkt exakt unter der Maus.

---

## 0. Verdict

**Conditional GO.** The researched algorithm — anchored geodesic slide with speed-limited pursuit — is sound and
sufficiently validated *as an algorithm* for a V1: region safety, on-surface exactness, Soft Selection by tangent
scaling, exact mirror pairs by writing the passive half, and the exact-restore gesture pattern are all measured and
match the code. Nothing found here contradicts the core recommendation.

It is **not** ready to be implemented as the report specifies it. Three technical premises of the report fail
against Production, and five Artist decisions change the architecture or the behaviour enough that they must come
first:

| # | Blocking item | Class |
|---|---|---|
| B1 | The reference must be the **drawn** triangulation (`viewport.derived.triangulate_face`), not the prototype's mirrored shorter-diagonal triangulation; the drawn one is itself mirror-asymmetric, so the symmetry rule must be "drawn surface for the driven half, exact mirror for the other" (§3.1) | MR (spec), no new code path |
| B2 | Full-mesh capture per gesture is too slow on the reference PC at ≥ 20k vertices once Production's own triangulation and the measured NumPy factor (≈ 3×, not 2×) are included; capture must be region-limited (§3.3) | MR (design) |
| B3 | Symmetry driver rule: `symmetric_influence` can drive vertices on both halves (K-near), the slide needs exactly one driver per pair (§3.5) | MR (spec, small) |
| B4 | Artist decisions E1 (reference lifetime / evaluation), E2 (surface under a morph mix), E3 (seam crossing), E5 (open boundaries), E6 (binding) (§5) | AD |

Everything else is either solvable during implementation or an acceptable, stated V1 limitation (§10).

---

## 1. Scope and method

- Read: the research report, the prototype source (`refsurf`, `geodesic`, `algorithms`, `fields`, `seam`, `harness`,
  `scenarios`, `studies`) and its 26 test functions (70 parametrised tests); Production: `viewport/derived.py`,
  `viewport/render_mesh.py`, `mirai/viewport/picking.py`, `mirai/topology/vertex_slide.py`,
  `mirai/controllers/gestures.py`, `mirai/interaction/tools/move.py`, `mirai/soft_selection/{influence,symmetric}.py`,
  `core/mesh.py` (journal, manifold rules); decisions AD-027, AD-032, `REFERENCE_HARDWARE.md` §4,
  `MODELING_ON_DEFORMED_SURFACES.md` §15, the O3 reference-PC results.
- Ran: the prototype tests under NumPy 2.5.3 **and** the pinned 2.2.6 (**70 / 70 pass** both, container) [M].
- Not repeated: any measurement the report already has with a reliable setup (§5–§12 of the report). New probes only
  where the report had no data: drawn triangulation symmetry, Production capture cost, an untested cursor mapping,
  thin-feature pursuit, transport continuity, a tree-free transport.
- Nothing ran on the reference PC. Every reference-PC figure below is container × 3 **[T]**, the factor
  `REFERENCE_HARDWARE.md` §4 records for NumPy parts (measured 2026-11-13).

---

## 2. Confirmed findings and unverified assumptions

### 2.1 Confirmed (measured and consistent with the code)

| Claim of the report | Status |
|---|---|
| Global closest point / normal ray jump on concave shapes; anchored candidates never do (0 region jumps, 76 scenarios) | **Confirmed** [M][V]: the anchor changes triangle only through `nbr` adjacency in `geodesic.trace`; there is no code path to an unconnected triangle. |
| Absolute geodesic is a function of the drag alone; zero drag restores the start bit for bit | **Confirmed** [M][V] (`test_absolute_geodesic_is_a_function_of_the_drag_alone`; explicit reset in `GeodesicPursuit.update`). |
| Pursuit caps a vertex's step at (1 + gain) × its tangent change | **Confirmed** [V]: `budget = (1 + gain)·|t − t_prev|`; the chase trace is limited to `min(budget, gap)`. Measured ≤ 2.0 everywhere [M]. |
| Tangent scaling keeps every soft weight on the surface; weight 0 never moves | **Confirmed** [M][V]. |
| (M) "drive one half, write the mirror" gives exact pairs | **Confirmed** [M][V]; identical to `vertex_slide.vertex_slide_positions`. |
| Seam vertices on the seam polyline stay exactly on the plane and the surface | **Confirmed** [M][V] (`seam.py`: convex combination of two plane points). |
| Cost independent of mesh size, linear in affected vertices | **Confirmed** for the update [M]; **not** for the capture (§3.3). |
| Prototype runs on the pinned NumPy | **Now confirmed in the container**: 70 / 70 under NumPy 2.2.6 [M]. Q9550 still open. |

### 2.2 Unverified or contradicted

| Assumption | Finding |
|---|---|
| "The drawn triangulation is fan from the first corner (convex) / ear clipping (concave)", re-stated in `refsurf._ear_clip` | **Partly wrong** [V]: Production fans *every* convex polygon from its first corner and ear-clips only concave ones, in the dominant-axis plane with ε 1e-12; the prototype cuts quads on the shorter diagonal and ear-clips every n-gon in the Newell plane (ε 1e-14). The prototype never slid on Mirai's drawn surface. |
| A mirror-symmetric reference triangulation makes the reference "what the artist sees" | **Contradicted** [M]: the drawn triangulation itself is asymmetric (§3.1). Symmetric reference ≠ drawn surface. |
| Reference PC ≈ 2× container | **Outdated** [V]: NumPy parts measured ≈ 3× (`REFERENCE_HARDWARE.md` §4, O3 results 2026-11-13). |
| Capture 19 ms – 403 ms | **Incomplete** [M]: excludes `core.Mesh` → arrays and Production triangulation; with them ≈ 200 ms (21.9k) and ≈ 1.0 s (87.5k) in the container (§3.3). |
| "Loops close exactly" through the pursuit | **Qualified** [V]: closure is exact because `update` resets on an exactly zero tangent; a loop that ends one pixel off zero keeps whatever lag is left. |
| Transport is "a discrete parallel transport, small holonomy over a soft radius" | **Not measured in the report; problematic on the cage** [M]: neighbouring vertices on different tree branches get directions 24–73° apart (§3.2). |
| Interface contract item 7: "`Application` owns the gesture" | **Outdated** [V]: since AD-027 gestures are `GestureSession`s in `controllers/gestures.py`; Surface Slide is a `_SlideGesture`. |
| Phong α = 0.5 | **Code default is 0.75** [V] (`Candidate`, `point_phong`); studies pass 0.5 explicitly. Port with 0.5. |
| Pursuit snap uses the straight-line gap: could it skip through a thin feature? | **Not observed** [M] (§3.7): 0 skips in 8 runs on a 2–5 % thick fin, 13–17 vertices legitimately crossed its rim. Not proven impossible [T]. |

---

## 3. Investigation

### 3.1 Reference surface consistency

**Facts.**

- Render, overlays, normals, CPU picking and the Knife take their triangles from one function,
  `viewport.derived.triangulate_face` / `triangulate_mesh_face` ("der eine Ort") [V]; the GPU ID pass rasterises the
  same triangles from `RenderMesh` [V]. `mirai/viewport/picking.py` already imports it, so a `src/mirai` tool may [V].
- Shading does not show the diagonal (flat = one Newell normal per polygon, smooth = bilinear normals over a quad,
  `render_mesh.py` docstring), but silhouette, depth and picking do [V].
- **Probe `probe_symtri.py` on the Gollum cage** (1 618 faces, 809 mirror pairs, no face straddles the plane) [M]:

| | triangles without a mirror image | drawn surface vs its own mirror image |
|---|---|---|
| Drawn rule (`triangulate_face`) | **3 170 / 3 318**; 766 of 809 face pairs (742 quads, 15 pentagons, 5 hexagons, 2 heptagons, the 13-gon and the 24-gon) | mean 0.020 h, p95 0.099 h, **max 0.48 h** |
| Prototype per-face rules | 200 / 3 318 | (report: 0.158 h max for mirrored results) |

  The fan starts at each face's first corner; a mirrored face is stored with reversed winding and usually a different
  first corner, so its fan diagonal is not the mirror of its partner's. **The display of a perfectly symmetric cage is
  already asymmetric**, by up to half an edge at non-planar quads, independent of Surface Slide.

**Consequence.** "Exactly the surface the artist sees" and "exact symmetry" cannot both hold for the *passive* half with
the current renderer. They can for the driven half.

**Smallest solution (recommended).**

1. The reference is built from `triangulate_mesh_face` of the captured faces — the drawn triangles, no second rule.
2. Under symmetry one half is driven (§3.5) and the other written as `mirror_position` of its driver (as Vertex Slide).
   Driven vertices therefore slide exactly on the drawn surface of their half. Passive vertices are exact mirrors;
   they lie on the mirror image of the drawn driven half, which is the drawn passive half up to the display's own
   asymmetry (mean 0.02 h, max 0.48 h on the cage). After the gesture the renderer re-triangulates as always.
3. With the seam as a barrier (E3), a driven vertex never needs the passive half of the reference, so **no mirrored
   triangulation is needed at all**: `refsurf.triangulate(..., partner)` is not ported.
4. Faces that straddle the plane (both sides, no seam vertex) cannot be triangulated symmetrically at all. The cage has
   none [M]; Production must refuse a gesture whose driven region contains one (status line) — **DI**.

**Alternative, not recommended for V1:** make `triangulate_face` mirror-equivariant (e.g. quads on the shorter
diagonal, which is invariant under reflection except for exact ties). It would make render, picking, Knife and GoZ
symmetric for every tool, but changes the drawn silhouette of every non-planar quad and the Knife's face geometry
(Knife oracle regression) — a renderer decision for Manu, separate from Surface Slide (**AD**, optional).

**Phong and "what the artist sees".** The geometry is flat, the shading is smooth. Flat evaluation slides on the
drawn geometry; Phong evaluation (report §10.2) slides on a surface that matches the smooth shading better but is off
the drawn facets by 0.06–0.49 h on the cage. Which one is "the surface the artist sees" is decision **E1**. If Phong is
chosen, it must use Production's vertex normals (`PackedGeometry`, area-weighted Newell) rather than the prototype's
angle-weighted ones, α = 0.5, and seam vertices must have their plane coordinate pinned (a seam vertex normal's
plane component is a float sum, not guaranteed 0) — **DI**.

### 3.2 Shape preservation

**Measured (report §6) [M].** Three separate effects: (a) the falloff dominates edge-length change for any soft drag —
the slide and a free move with the same weights distort alike; (b) the direction model: `transport` is an isometry on
developable surfaces (cylinder 0.1 %) and best or near-best elsewhere; (c) curvature: a fully selected patch distorts
∝ (distance / curvature radius)² (sphere 2 % mean after 3 edges, 12.7 % after 8; cage brow 15.7 % / 62.8 % after
1.7 edges; dense mesh 0.12 % at 3 edges).

**Assessment.**

- For the intended use — soft-selected regions moved by a few edges — distortion is the falloff's, not the algorithm's.
  `transport` is **sufficient for V1** [M].
- Preserving every edge length is impossible on a surface of varying curvature (Gauss); on constant-curvature pieces
  (plane, cylinder, sphere) a rigid motion exists. Equal-length parallel geodesics are not that motion on a sphere:
  they converge. **V1L**.
- A correction is justified only if the practical test shows visible distortion of fully selected patches over 2+
  edges on coarse cages (**AD**, after the test). Ranked options [T]:
  1. *Pivot-centred exponential-map decal* (polar coordinates around the pivot, re-laid around the moved pivot with
     the transported frame): rigid on spheres and developable surfaces, preserves distances from the pivot, no
     iteration; needs a discrete log map at `begin`. Side effects: shear grows with distance from the pivot on
     varying curvature; applies cleanly only to the weight-1 core (blending it with the falloff must stay in the
     tangent domain or it leaves the surface — report §11.1).
  2. *On-surface edge relaxation of the weight-1 core*, recomputed from the start state every frame (stays absolute).
     Side effects: fights the intended falloff stretch if not restricted to w = 1 edges; iteration count becomes part
     of the result; extra traces per frame; moves vertices across creases; seam and boundary vertices need their 1D
     rules inside the relaxation.
  Neither belongs in V1.

**New finding — the tree transport is discontinuous [M] (`probe_holonomy.py`).** The transport rotates the pivot's
drag along the Dijkstra tree. Two neighbours on different branches around a strongly curved point receive directions
that differ by the curvature the branches enclose. Largest direction jump between neighbouring vertices:

| Cage, seed at | radius 0.09 (the report's scenarios) | radius 0.15 |
|---|---|---|
| nose tip | 35° | 68° (52 edges > 10°) |
| upper lip | 40° | 40° |
| nose side | 32° | 34° |
| lower eye rim | 24° | 73° |
| brow | 24° | 30° |
| cheek | 9.5° | 11° |
| sphere (1 538 v), r = 0.5 R / 1 R | 3.2° | 12.8° |

Most worst edges carry low weights (0.01–0.1), which is why the distortion tables do not show it strongly, but some
carry 0.23–0.39: two neighbours of weight ≈ 0.4 dragged 2 h each move ≈ 0.8 h; 40° apart they separate by ≈ 0.5 h —
a visible kink.

**Tree-free alternative [M] (`probe_direct.py`).** Rotate the pivot's drag into each vertex's tangent plane by the
*direct* minimal rotation pivot normal → vertex normal (the prototype already uses this as its fallback). It is
continuous in the normal, exact on cylinders, needs no tree and no Python loop:

| | tree | direct |
|---|---|---|
| largest neighbour jump, cage r = 0.15 (nose tip / lid / lip) | 68° / 73° / 40° | 28° / 49° / 39° |
| rigid patches: cylinder circ., sphere 3 edges, cage cheek / forehead / brow (mean / max) | 0.1/0.1, 2.0/8.4, 8.5/18.2, 3.2/10.2, 15.7/62.8 % | 0.1/0.1, 2.0/8.1, 8.0/19.6, 3.0/7.9, 13.8/62.8 % |
| sphere 8 edges (mean / max) | 12.7 / 35.7 % | 12.7 / 41.8 % |
| soft scenarios, all edges mean | — | within ±4 points of the tree in all 15 |
| loops: step ratio, closure | 1.71–2.0, 0 | identical |
| begin, 545 / 5 669 vertices (100k mesh) | 11.8 / 122 ms | **0.24 / 1.35 ms** |

Its defect: undefined where a vertex normal is opposite to the pivot's (the U with a one-cell gap has 9 such vertices
in the soft patch; the prototype falls back to identity), and numerically unstable close to that. **DI:** implement
the direct rotation with a fallback to a two-step rotation (via the tree parent, or via an intermediate normal) where
`n_pivot · n_i < −0.5`; gate the choice on the report's 76 scenarios plus the jump metric above. Until then the
report's tree transport stays the reference behaviour.

### 3.3 Interactive performance

**Report numbers [M] (container).** Update: 1 000 affected vertices 3–7 ms for drags ≤ 10 h; 10 000: 22–63 ms;
worst frame of a 30 h drag 13.7–27.6 ms (1 000) and 101–195 ms (10 000). Begin: weights 1.2–3.5 ms and transport
21–35 ms per 1 000 vertices; 212–275 ms per 10 000. Capture 19 ms (5k) – 403 ms (100k).

**Production costs the bench left out [M] (`probe_capture.py`, container):**

| Mesh | `core.Mesh` positions → array | faces → index lists | `triangulate_mesh_face`, every face | reference build | journal write, 1 000 vertices |
|---|---|---|---|---|---|
| Gollum 21 875 | 3.6 ms | 5.2 ms | 68 ms | 120 ms | 0.28 ms |
| Gollum 87 500 | 14.5 ms | 26 ms | 496 ms | 496 ms | 0.33 ms |

A full-mesh capture per gesture is therefore ≈ 200 ms (21.9k) and ≈ 1.0 s (87.5k) in the container, **≈ 0.6 s and
≈ 3 s on the reference PC** [T, ×3]. That is a press hitch the tool cannot have. **B2 / MR.**

**Optimisation before any new dependency or parallelism (in order of value):**

1. **Region-limited capture.** Capture only the faces within a geodesic margin of the affected set (the Dijkstra of
   the weights already visits them); mark the captured region's border edges as a distinct `CAPTURE` barrier. A trace
   that reaches it grows the capture (radius × 2) and the frame is recomputed — rare, and the result is identical to a
   full capture (gate G2). Cost becomes O(region), like the update. Precedent: the report's own §14.7 [T].
2. **Tree-free transport** (§3.2): begin 50–90× cheaper, no Python loop [M].
3. **Target extension for unchanged direction.** A straight drag extends the same geodesic; continue from the last
   target end instead of re-tracing from the start (the cost of the absolute evaluation grows with distance:
   2.2–3.7 µs per vertex at 2 h, 6.6–11.9 µs at 30 h [M]). The result differs from a full re-trace only by rounding;
   zero drag still resets exactly. Gate: path spread ≤ 1e-9 h against the full trace.
4. **Reuse arrays that exist**: for a shown morph mix, `MixSurface.position_array()` [V]; vertex normals from
   `RenderMesh.packed` where a viewport exists, computed otherwise.
5. **Persistent, journal-refreshed reference** (adjacency per topology version, geometry rows refreshed from
   `Mesh.watch()`): only if E1 chooses a kept reference — it is the larger design (faces around moved vertices can
   change their triangulation, `RenderMesh._retriangulate` is the precedent).

The per-vertex Python loop of Dijkstra and transport, and the per-crossing NumPy call overhead (one pass = a dozen small
array calls), are the ceiling at small sizes; on the Q9550 that overhead dominates at ≤ 1 000 elements per call
(O3 results). No native code, threads or new packages are warranted before items 1–3 are measured on the reference PC.

**Large soft regions.** 10 000 affected vertices: update 22–63 ms container → ≈ 70–190 ms reference PC [T]. That is the
same class as a Soft Move of 10 000 vertices, whose write + sync path (≈ 2.6 µs per moved vertex for `_sync_geometry`
after O3 on the reference PC, plus the edit mesh's per-vertex reads) the slide shares. Usable, not smooth — **V1L**,
with the acceptance criteria of §8.

### 3.4 Cursor mapping

**Report [M]:** with the Move-tool mapping the pivot covers 0–92 % of the screen drag on the 18 front-view drags; the
Newton solve for "pivot under the cursor" works in 10 of 18 and races once at 112×.

**New probe [M] (`probe_cursor.py`), same 18 drags, `geodesic_pursuit[transport]`:**

| Mapping | within 10 % of the cursor | within 25 % | median follow | largest step / cursor step | worst case |
|---|---|---|---|---|---|
| M1 — Move tool: screen delta at the pivot's start depth, projected into its start tangent plane | 3 / 18 | 6 / 18 | 0.66 | 1.0 | cage lip down 0.00 (does not move) |
| M2 — ray through the cursor intersected with the pivot's start tangent plane, clamped to 3× | 6 / 18 | 11 / 18 | 0.82 | 3.0 (temple, surface at 76° to the view) | cage lip down **−0.36 (moves against the drag)** |

M2 removes the first-order foreshortening (the cos θ M1 loses); what is left in both is curvature: the geodesic from
the start turns away from the view (brow into socket 0.42 in both). M2 can reverse on screen where the path wraps over
a fold. Both mappings are absolute and linear in the pixel drag, so zero drag stays exact, and both live entirely in
the gesture: **the algorithm takes a tangent vector and knows no camera** (unchanged from the report's contract).

**Assessment.**

- Acceptable for V1: the pivot lagging behind the cursor on tilted or curving surfaces (M1 never moves faster than the
  cursor, never reverses) — **V1L + AD (E4)**.
- Would make the tool unsuitable: motion against the drag, speed spikes, or a pivot that jumps to another surface
  under the cursor. M1 has none of these [M]; M2 has the first two at folds; `ray_view` / closest point has the
  third (report §5). **Recommendation: V1 ships M1** (no new infrastructure: `camera.screen_delta_to_world` at the drawn
  pivot depth, as `MoveTool._on_update`), M2 as a candidate for the practical test only if Manu reports the lag as
  the main problem.

### 3.5 Existing Mirai systems

| System | Compatibility | Class |
|---|---|---|
| **Soft Selection** | `compute_influence` / `symmetric_influence` give the weights unchanged (geodesic default, smooth curve, flow ratio, mask via `mask_weights`). The tree transport needs a second Dijkstra from the pivot (or parents from `_geodesic_distances`); the direct transport needs neither. Live radius change (wheel) = rebuild the plan from the press state and replay, the `SmoothGesture.reweight` pattern; the pursuit's next budget includes the weight change, so no pop [V]. Euclidean metric can give weights to other shells (eyeball, teeth): those vertices slide on their own shell — state it. | DI |
| **Symmetry, driver rule (B3)** | `symmetric_influence` drives the seed side, and with seeds on both halves drives each vertex from its nearer source (K-near); a selected vertex *and* its partner are both seeds [V]. A transported tangent from one pivot is wrong on the far half (it is not mirrored). Rule needed: **drive the pivot's half plus the seam; every vertex on the other half is written as the mirror of its partner, whatever K-near says**; weights stay pair-consistent. | MR (spec) |
| **Seam** | Seam vertices = `SEAM` correspondence on declared seam edges; slide on the seam polyline (`seam.py` logic) with the transported tangent's in-plane component; plane coordinate pinned exactly as `vertex_slide_positions` does. Seam ends / branches stop (flag). Seam polyline must use the *declared* seam edges (`definition.seam_edges`), not x == 0 edges. | DI |
| **Seam barrier back-off** | A barrier stops driven vertices exactly on the plane, where they coincide with their partner → `AMBIGUOUS` (report §9.4). Rule: stop short of the barrier edge by a fixed fraction of the triangle height along the incoming direction (precedent `SYMMETRIC_MAX_AMOUNT = 0.98`); the stopped anchor stays in its triangle, so the position stays on the surface. | DI (+ E3) |
| **Topology / change journal** | Positions only; `_SlideGesture` already does `begin_change` at the first motion, `set_vertex_position` per frame, `end_change` → one `MeshDeltaCommand` at release, `rollback_change` on Esc, `release_change` on cleanup [V]. A held gesture refuses topology commands, Undo / Redo (`BEGUN_GESTURE_REFUSES`) [V], so the reference cannot go stale mid-gesture. No Core change. | — |
| **Manifold rules** | Core edges carry ≤ 2 faces [V]; bowtie vertices and multiple shells are possible ("keine allgemeine Non-Manifold-Prüfung"). Shells: correct by construction (traces follow adjacency). Bowtie vertex in the driven region: one tangent plane averages two fans — refuse the gesture with a status line. | DI |
| **Morph mix** | §15 (2026-11-03): queries and drag mappings read the drawn mix; writes go to the base; a base edit moves a drawn point by its rest delta (constant offset) [V]. Sliding on the *mix* and writing `q − offset` leaves base vertices off the base surface; sliding on the *base* keeps them on it but the drawn vertex leaves the drawn surface by the offset change across the region. A real semantic choice. | AD (E2) |
| **Pose** | Posed, bound edit mesh: every position command refused (AD-028 S5) [V]. Surface Slide inherits the refusal; nothing new. | — |
| **SubD preview** | §15 (d): picking on the (mixed) cage, not the limit surface. Surface Slide slides on the cage; the limit surface follows. Sliding on the limit surface would need SubD provenance (MODELING_ON_DEFORMED_SURFACES R-9). | V1L (confirm, E8) |
| **Hidden / mask** | Vertex Slide: hidden neighbours are no target; masked vertices move `1 − m` [V]. Surface Slide: hidden faces are not captured (their edges act as barriers); weight × (1 − mask). | DI |
| **Undo / Redo / cancel** | As `_SlideGesture` (above). Esc restores via the journal; zero drag restores via the reset; both bit-exact [V][M]. Anchors and pursuit state are gesture-local, never in history. | — |
| **Picking during the gesture** | `_write` calls `invalidate_picks()` and `notify_vertices_moved` per frame [V]; same cost profile as Vertex Slide. | — |
| **NumPy location** | `src/mirai` takes NumPy only from `viewport.packed_geometry` (AD-032 §11.3, one guarded import site) [V]. The port must import it from there. | DI |
| **Input** | A new command needs a binding; `config/keymap.json` entries only after Manu's explicit approval (CLAUDE.md, AD-013 addendum). `G` in vertex mode is Vertex Slide, `Ctrl`/`Alt`/`Ctrl+Alt+G` are taken. | AD (E6) |

### 3.6 Reference lifetime and boundary behaviour

| Topic | Technical finding | Behaviour question | Class |
|---|---|---|---|
| Flat vs Phong | Flat = the drawn geometry exactly; sinks h²/8R below smooth shapes for vertices that leave their position. Phong (α 0.5) reproduces the sphere to 4th order, costs nothing per frame, but leaves the facets by up to 0.49 h at the cage's eye rim and rounds creases unless crease-aware [M]. | Which surface counts as "the" surface | AD (E1) |
| Per gesture vs persistent | Per gesture: trivially correct, fits the journal, no invalidation; erodes coarse convex regions over many gestures (386-vertex sphere: mean radius 0.987 after 60 gestures; 1 538 v: 0.9993; cage: moved vertices 0.036 h from the original after 60) [M]. Kept: bounded loss, but every other edit (Move, Smooth, Knife) invalidates or must re-anchor — a new subsystem. | Whether erosion on coarse cages matters in practice | AD (E1); per gesture **V1L** |
| Repeated gesture erosion | Per gesture flat behaves like a weak smoothing filter on the moved vertices only; dense meshes are unaffected in practice (0.9993 at 1.5k). | — | V1L |
| Sharp creases | Tracer exact across 1- and 2-segment creases [M]; flat slides over them without instability. Phong bulges there. | Should a crease stop the slide? (not asked yet) | V1L (flat) |
| Mesh boundaries | A path reaching a boundary stops (flag). A boundary vertex dragged outward is **blocked entirely** — its along-boundary component is lost too [V] (`launch_from_vertices`: `length = 0`). On the cage the boundaries are the eye and mouth openings, i.e. lid and lip lines. The seam walker is a generic edge-chain walker; boundary loops are edge chains: boundary vertices can slide along their boundary with the same code. | Slide along / stay fixed | AD (E5), then DI |
| Non-manifold | Edge > 2 faces impossible in Core [V]; bowtie → refuse (§3.5). Inconsistent winding handled by the tracer (`nbr_flip`) but untested — Core faces are consistently wound by construction [T]. | — | DI (+ test) |
| Across the seam | Free crossing: halves interpenetrate (pairs stay exact). Barrier: needs the back-off (§3.5). | Allow crossing? | AD (E3) |
| Pursuit lag at release | Worst measured: 10 of 37 vertices up to 1.43 h behind, 7 settle steps to close [M]. Settling at release changes the result after the artist let go; committing what is shown keeps WYSIWYG. | Commit as shown / settle | AD (E7) |

### 3.7 Prototype review

The code matches the report's description of the tracer, the pursuit, the seam walk, the Phong evaluator and the
transport [V]. Findings beyond the report:

1. **Closure by reset** (§2.2): exact loop closure is the explicit zero-tangent reset. Add a Production test for a loop
   that ends near (not at) zero: lag stays bounded by the pursuit rule.
2. **Pursuit snap on the straight-line gap**: `reach = |target − current| ≤ budget` compares a chord with a surface
   budget. Across a thin feature a torn target could be adopted without travelling. Probe (`probe_thin.py`, fin 2–5 %
   thick, 28–30 vertices, 240-frame turning drags): **0 occurrences**, while 13–17 vertices crossed the rim along the
   surface [M]. Cheap guard for Production: adopt the target directly only if the vertex was not lagging and the target
   anchor's triangle shares a vertex with the previous target's, else chase — **DI**.
3. **Chase direction degenerate** when the gap is along the current triangle's normal (`_unit` of ≈ 0): the vertex
   stays and stays lagging. Fallback: chase along the target's own last direction reversed — **DI**.
4. **Flags**: `_chase` reports the *target's* flags; the chase trace's own flags are dropped, and lagging is an attribute,
   not a flag. Production returns per-vertex `BOUNDARY | BLOCKED | STUCK | LAGGING` as the contract says — **DI**.
5. **Phong α default 0.75** in the classes; 0.5 recommended — port with 0.5.
6. **Boundary vertex blocked entirely** (§3.6).
7. **Tests**: the mirror test checks the mirrored positions with the *global* closest point, the very query the report
   shows cannot tell regions apart; fine on a symmetric reference, not a template for Production tests (use the
   tracked deviation). No test covers: boundary hits, seam ends, barrier back-off, bowtie / flipped neighbours, near-zero
   loops, weight change mid-gesture, the transport continuity. All needed in Phase 1–2 (§9).
8. **`_ear_clip` / `triangulate`** do not reproduce Mirai's rule (§2.2) — not to be ported; use `triangulate_face`.
9. **Interface**: `SlideReference.capture(surface, mirror_partner, seam_edges)` should take the captured face set and
   barrier edges instead of a partner map (no mirrored triangulation, §3.1).

---

## 4. Critical technical blockers

1. **B1 — reference triangulation.** Spec the reference as "drawn triangles of the captured faces", the symmetry rule
   as "driven half on the drawn surface, passive half exact mirror", refuse straddling faces. No implementation risk;
   without it the tool slides on a surface that is not drawn (up to 0.25 h on the cage, report §9.2).
2. **B2 — capture cost.** Region-limited capture with a growable `CAPTURE` barrier is part of the architecture, not an
   optimisation added later; otherwise every press on a 20k+ mesh hitches 0.6–3 s on the reference PC [T].
3. **B3 — one driver per pair.** Spec the driven set independent of K-near.

No algorithmic blocker was found: the region-safety and exactness claims hold against the code.

---

## 5. Decisions required from Manu

| # | Question | Options | Recommended default (agent) | Needed before |
|---|---|---|---|---|
| **E1** | Reference lifetime and evaluation | (a) per gesture, flat · (b) per gesture, smooth (Phong) · (c) kept until topology changes | (a): exactly the drawn geometry; erosion only on coarse cages after many gestures | implementation (c changes the architecture) |
| **E2** | Surface while a morph target is dialled in | (a) slide on the base (rest) surface, cursor mapped at the drawn depth · (b) slide on the drawn mix, base = result − offset · (c) refuse above 0 % | (a): base vertices stay on the base surface the offsets are defined against | implementation |
| **E3** | Crossing the mirror plane | (a) stop short of the seam (as Vertex Slide's 98 %) · (b) cross freely (halves can interpenetrate) | (a) | implementation |
| **E4** | First version without "pivot exactly under the cursor" | yes / no; mapping M1 or M2 | yes, M1; judge in the practical test | practical test |
| **E5** | Vertices on open boundaries (eye, mouth openings) | (a) slide along the boundary · (b) stay fixed · (c) as prototype (stop only when pointing out) | (a) | implementation |
| **E6** | Binding and tool entry | a key / modifier / mode beside `G` (Vertex Slide), entered by Manu in `keymap.json` | — (Manu's layer) | Phase 3 |
| **E7** | A vertex still lagging at release | (a) commit as shown · (b) settle first | (a) WYSIWYG | Phase 3 |
| **E8** | SubD preview on | slide on the cage (consistent with §15 (d)) | confirm | Phase 3 |
| E9 | Direction model | `transport` (decal) / `project` (each vertex follows the screen direction in its own plane) | `transport` (report) | already recommended; confirm |
| E10 | Shape correction for far drags of fully selected patches | none / decal / relaxation | none in V1; after the practical test | V1.1 |
| E11 | (optional, renderer) mirror-equivariant drawn triangulation | keep fan / shorter diagonal | keep (separate topic) | — |

### 5.1 Phase 0 — Manu's decisions (2026-11-14)

**Manu (chat, entered by the agent):** „Ich würde die vorgeschlagenen Defaults E1–E3, E5 und E8–E11 übernehmen. E4, E7
und E10 behalten wir als Punkte für deinen Praxistest. E6 entscheiden wir erst bei der tatsächlichen
Bedienungsintegration. Damit können wir Phase 0 sauber abschließen und anschließend Phase 1 umsetzen.“

| # | Decision | Status |
|---|---|---|
| E1 | Reference **per gesture, flat** evaluation (the drawn geometry); no Phong, no kept reference in V1 | **decided** |
| E2 | With a morph target dialled in: slide on the **base (rest) surface**; the cursor is mapped at the drawn depth (§15 mapping) | **decided** |
| E3 | **No crossing** of the mirror plane: driven vertices stop short of the seam (back-off, precedent 98 %) | **decided** |
| E4 | V1 without pivot-under-cursor, mapping M1 | **default for the build; verdict in the practical test (Phase 5)** |
| E5 | Vertices on open boundaries **slide along the boundary** (edge-chain walker, as the seam) | **decided** |
| E6 | Binding / tool entry | **decided 2026-11-15** (Phase 3, Manu: „J“): hold `J`, its own key beside `G`; in `config/keymap.json` with `"set": "2026-11-15"` (§13.5) |
| E7 | Lagging vertex at release: commit as shown | **default for the build; verdict in the practical test** |
| E8 | SubD preview on: slide on the cage | **decided** |
| E9 | Direction model `transport` | **decided** |
| E10 | No shape correction in V1 | **decided for V1; whether V1.1 needs one is judged in the practical test** |
| E11 | Drawn triangulation unchanged (fan); no renderer change for this tool | **decided** |

**Reading** (`PROVISIONAL`, Manu corrects in one sentence): "Phase 0 sauber abschließen" includes accepting the
technical specs B1–B3 of §4 (drawn triangles; driven half on the drawn surface, passive half exact mirror; straddling
faces refused; region-limited capture; one driver per mirror pair, the pivot's half plus the seam). E10 appears in
both lists of the quote: read as "the default (none in V1) holds, the practical test decides about later".

---

## 6. Recommended V1 scope

**In:**

- Vertex mode (and edge / face selections resolved to their vertices, as W/E/R do with `resolve_selection_vertices`);
  hovered vertex as fallback seed.
- `geodesic_pursuit[transport]`, gain 1, flat evaluation, per-gesture reference, region-limited capture from the drawn
  triangulation.
- Soft Selection (all metrics / curves / flow the app offers, live radius), mask, hidden faces as barriers.
- Symmetry: one driven half, exact mirrored writes, seam vertices on the declared seam polyline, seam barrier with
  back-off (if E3 = a); refuse without partner, on straddling faces, bowtie vertices in the region, non-exact plane.
- Boundaries per E5 (recommended: along the boundary chain with the seam walker).
- Cursor: M1 at the drawn pivot depth.
- Morph mix per E2; pose refused (existing S5); SubD on: cage.
- One history entry, Esc / zero drag bit-exact, status line with the flags (boundary stop, lagging count).

**Out (V1 limitations, stated in the tool's status / docs):** Phong and kept references (unless E1 says otherwise),
sliding on another object (retopology), sliding on the SubD limit surface, pivot-under-cursor solve, shape correction,
crossing the seam (unless E3 = b), crease-aware stopping.

---

## 7. Proposed implementation architecture

```
src/mirai/surface_slide/            pure: no viewport drawing, no GUI, no input types; NumPy from viewport.packed_geometry
  reference.py   SlideReference      immutable arrays of a captured face set: V, T (drawn triangles), N, E, Pin, G, nbr
                                      (−1 boundary, −2 barrier: seam / hidden, −3 capture border), vertex→triangles CSR,
                                      VN, VertexId <-> row; capture(mesh_like, faces, barriers) via triangulate_mesh_face
  tracer.py      trace / launch      port of geodesic.py (flags BOUNDARY, BARRIER, CAPTURE, BLOCKED, STUCK, MAXITER)
  curves.py      EdgeChain           port of seam.py, used for the seam and (E5) open boundaries
  plan.py        plan_surface_slide  seeds + Soft weights (compute_influence / symmetric_influence) + mask + hidden +
                                      SymmetryIndex -> SlidePlan(driven, weights, pivot, seam/boundary chains, mirrors,
                                      plane); raises SurfaceSlideRefused(status line)
  slide.py       SurfaceSlide        transport frames (direct rotation with fallback, §3.2), pursuit, update(tangent),
                                      settle(), capture growth on a CAPTURE flag, SlideFrame(positions, flags, lagging)
src/mirai/controllers/gestures.py   SurfaceSlideGesture(_SlideGesture): arm -> plan + capture; step -> M1 mapping
                                      (camera.screen_delta_to_world at the drawn pivot depth, shown_shift) -> tangent ->
                                      update -> mirrored writes -> _write; release / abort / cleanup inherited
```

**Reused unchanged:** `triangulate_mesh_face`, `compute_influence`, `symmetric_influence`, `mask_weights`,
`SymmetryIndex`, `mirror_position`, `is_exact_plane`, `_SlideGesture` (journal, history, Esc), `shown_shift`,
`camera.screen_delta_to_world`, `MeshDeltaCommand`, the `GestureController` arming and slot rules.
**Changed outside the new package:** `gestures.py` (one gesture class, one arm method), the command / binding registry
(after E6), docs. Possibly `soft_selection.influence._geodesic_distances` gains an optional parent output, only if the
tree transport is kept. **No Core change, no new dependency, no second triangulation rule, no spatial index.**

Data flow is Core → (capture, read only) → `surface_slide` → positions → Core writes through the journal; the
viewport is informed through the existing `notify_vertices_moved`. Nothing flows back from the viewport except what
the gesture already reads (camera, drawn mix via `query_mesh`).

---

## 8. Performance acceptance criteria (reference PC)

Measured on the Q9550 with the Production interpreter (Python 3.12.10, NumPy 2.2.6, `.venv312`), p95 over ≥ 60
frames, with a probe in the `experiments/drag_cost` style, panels on. Meshes: `gollum_20k` and the 87.5k fixture.
Container proxy for development = target ÷ 3 [T].

| # | Criterion | Target |
|---|---|---|
| P1 | Arm (press → ready: capture, weights, transport), 1 000 affected vertices, 20k and 87.5k | ≤ 100 ms |
| P2 | Arm, 10 000 affected | ≤ 300 ms |
| P3 | Slide compute per motion (`update`, excluding write and viewport), 1 000 affected, drag ≤ 10 h / ≤ 30 h | ≤ 10 ms / ≤ 20 ms |
| P4 | Same, 10 000 affected, drag ≤ 10 h | ≤ 100 ms |
| P5 | Whole frame (motion → drawn) against a Soft Move (W) with the same seeds and radius | ≤ Soft Move + 10 ms (1 000 affected) |
| P6 | Mesh-size independence: P3 at 20k vs 87.5k | within 25 % |
| P7 | Release (commit) / Esc | ≤ 50 ms; Esc and zero drag bit-exact |
| P8 | Memory per gesture | ≤ 1 KB per captured vertex; no whole-mesh copy for a regional gesture |

Basis: report §12 update numbers × 3 give ≈ 12–20 ms for P3 at 10 h today (8–16 ms at 2 h), so P3 needs optimisation 3
(§3.3);
P1 / P2 require region capture and the tree-free transport; P4 is the "usable, not smooth" class already accepted for
Soft Move at that size.

---

## 9. Phased implementation plan with regression gates

| Phase | Content | Gate (must pass before the next phase) |
|---|---|---|
| **0 — Decisions** | E1, E2, E3, E5 answered; this audit's B1–B3 specs accepted; E6 when Phase 3 starts | Manu's answers recorded in this file — **done 2026-11-14 (§5.1)** |
| **1 — Pure core** | Port `reference`, `tracer`, `curves`, pursuit to `src/mirai/surface_slide/` on index arrays; transport per §3.2 | **G1**: on the report's 76 scenarios the port matches the prototype (oracle, like `knife_oracle`) to ≤ 1e-12 h for every geodesic candidate kept; prototype claims re-asserted (0 region jumps, step ratio ≤ 2, exact zero restore, weight 0 untouched, tracked deviation ≤ 1e-12 h); new tests: thin fin, boundary hit, near-zero loop, chase degenerate gap, transport jump metric (direct vs tree), antipodal normals |
| **2 — Plan, capture, symmetry** | `plan_surface_slide`, region capture from `core.Mesh` with `triangulate_mesh_face`, seam / boundary chains, barrier back-off, refusals | **G2**: on the Gollum cage and `examples/meshes/head_basemesh.obj`: mirror pairs bitwise exact, seam coordinate exactly 0, no `AMBIGUOUS` after a barrier stop, every driven vertex on the *drawn* triangles of its face (≤ 1e-12 h), region capture == full capture bit for bit, `tests/mesh_invariants.py` after every gesture, refusals tested |
| **3 — Gesture** | `SurfaceSlideGesture`, M1 mapping at the drawn depth, morph-mix rule (E2, tested on `scenes/Gollum_Head_01_Morphs.mirai.json`), binding (E6) — **done 2026-11-15 (§13.5)** | **G3**: one history entry; Undo / Redo exact; Esc and zero drag bit-exact (`export_state` equality); held-gesture refusals; posed refusal; mix 0 % ≡ no target; `pytest tests` fully and GL tests in their own process (AGENTS.md §8a), `experiments/morph_lab/tests`, the Knife oracle (shared triangulation untouched) |
| **4 — Performance** | Optimisations 1–3, probe | **G4**: container proxies of P1–P8; then a reference-PC run by Manu against P1–P8 |
| **5 — Practical test** | Short German test for Manu: cheek, brow, lid rim, lip, nose; with and without symmetry; soft radii; at 0 % and 100 % mix | **G5**: Manu's verdicts on E4, E7, E10 recorded; keymap entry only after his explicit approval |
| 6 — V1.1 (optional) | Phong / kept reference / cursor M2 / shape correction, each only on a recorded need | per item |

---

## 10. Open-problem register

Since 2026-11-14 the **AD** rows are settled as recorded in §5.1 (E4, E7, E10 by the practical test, E6 at Phase 3).

| Problem | Class |
|---|---|
| Reference = drawn triangulation; symmetry via driven half + mirror; straddling faces refused | **MR** (spec) |
| Region-limited capture (cost at ≥ 20k on the reference PC) | **MR** (design) |
| One driver per mirror pair, independent of K-near | **MR** (spec) |
| Reference lifetime / flat vs Phong | **AD** (E1) |
| Surface under a morph mix | **AD** (E2) |
| Seam crossing; back-off distance | **AD** (E3); back-off **DI** |
| Open-boundary vertices | **AD** (E5); implementation **DI** (seam walker) |
| Binding | **AD** (E6) |
| Lag at release | **AD** (E7) |
| Cursor fidelity (pivot lags on tilted / curving surfaces) | **V1L** + **AD** (E4) |
| Tree transport discontinuity; direct rotation with antipodal fallback | **DI** (gate G1) |
| Pursuit snap guard (thin features), chase degeneracy, flag reporting | **DI** |
| Phong details (Production normals, α 0.5, seam pinning) — if E1 chooses Phong | **DI** |
| Bowtie vertices, flipped neighbours | **DI** (refuse; test) |
| Hidden faces as barriers, mask scaling | **DI** |
| NumPy import site (`viewport.packed_geometry`) | **DI** |
| Shape distortion of fully selected patches over long drags | **V1L**, **AD** after the test (E10) |
| Erosion over repeated per-gesture slides on coarse cages | **V1L** |
| SubD limit surface, retopology onto another object, pose | **V1L** (pose: existing refusal) |
| Display asymmetry of the drawn triangulation (all tools) | outside this tool; **AD** optional (E11) |
| Reference-PC run of the slide itself | **DI** (Phase 4) |

---

## 11. Corrections to the research report

1. Reference-PC factor for NumPy code: ≈ 3× (REFERENCE_HARDWARE §4, 2026-11-13), not 2× (report §2, §12).
2. `refsurf._ear_clip` / `triangulate` do not restate Mirai's rule; Production fans convex polygons from the first
   corner (report §9.2 compares the fan for quads only).
3. Mirai's drawn triangulation is not mirror-symmetric; the recommendation "triangulate mirror-symmetrically" yields a
   reference that differs from what is drawn. Use the drawn one for the driven half (§3.1).
4. Loop closure is exact by the zero-drag reset, not by the pursuit (§2.2).
5. Contract item 7: the gesture is a `_SlideGesture` in `controllers/gestures.py` (AD-027), not `Application`.
6. Capture cost excludes `core.Mesh` → arrays and Production triangulation (§3.3).
7. The tree transport's direction jumps were not measured (§3.2).
8. NumPy 2.2.6: the prototype's 70 tests pass in the container (closes half of report §13.9).

---

## 13. Handoff: Phase 1 (pure core)

Mode (M5): Production, a new package; no existing behaviour changes. Decisions: §5.1. Read this file §3.1, §3.2,
§3.5–§3.7, §7, §9 and the report §4, §14.4–§14.5; the prototype source is the reference implementation.

**Build** `src/mirai/surface_slide/` on index arrays (no `core.Mesh`, no camera, no GUI); NumPy only through
`viewport.packed_geometry` (AD-032):

- `reference.py` — `SlideReference` from `V (n, 3)`, `T (m, 3)` (the caller supplies the drawn triangles) and edge sets
  that act as barriers (seam, hidden) or as the capture border; immutable arrays; flat evaluation only (E1). Not
  ported: closest-point grid, ray intersection, Phong, `refsurf.triangulate` / `_ear_clip`, the mirrored triangulation.
- `tracer.py` — port of `geodesic.py` with distinct flags `BOUNDARY`, `BARRIER`, `CAPTURE`, `BLOCKED`, `STUCK`,
  `MAXITER`; a blocked boundary start no longer drops the along-boundary component (handled by the chain walker, E5).
- `curves.py` — `EdgeChain`: the `seam.py` walker generalised to any chain of edges (declared seam, open boundary
  loops, E5); the seam's plane coordinate stays exact.
- `slide.py` — `SurfaceSlide`: transport by the direct minimal rotation with a fallback where `n_pivot · n_i < −0.5`
  (§3.2), frames also injectable (for the oracle); pursuit gain 1 with the snap guard (§3.7 item 2), the degenerate-gap
  fallback (item 3), exact reset at zero tangent, `settle()`; barrier stop with back-off (E3); per-vertex flags incl.
  `LAGGING`; `SlideFrame(positions, flags, lagging)`.

**Not in Phase 1:** planning from a `core.Mesh`, region capture, the symmetry driver rule (Phase 2); the gesture,
mapping and binding (Phase 3, E6).

**Tests.** `tests/test_surface_slide_*.py`, self-contained (nothing in `tests/` imports `experiments/`, AGENTS.md §8a):
small generated sphere / cylinder / U / thin fin; exact unrolled geodesics on the U, zero drag bit-exact, weight 0
untouched, step ≤ (1 + gain) × tangent change, tracked deviation ≤ 1e-12 h, read-only arrays, boundary and barrier stops
(back-off strictly off the plane), chain walker on a seam (coordinate exactly 0) and on a boundary loop, transport
continuity and the antipodal fallback, near-zero loop lag bound, no skip through the fin, flags. **Gate G1** lives
beside the prototype, like the Knife oracle: `experiments/surface_slide/tests/` compares the Production modules with
the prototype on the 76 scenarios (injected tree frames: ≤ 1e-12 h; direct frames: the report's metrics no worse than
§3.2's table). Runs: the new files, `experiments/surface_slide/tests`, `tests/test_packed_geometry.py` (NumPy import
rule).

**Done means:** G1 green; the package docstring states the contract (report §14.4 as amended here); an implementation
note appended to this section. No `ATELIER.md` entry (nothing visible yet).

### 13.1 Implementation note — Phase 1 done (2026-11-15)

**Built** (Production, new package, no app wiring, no binding, no `keymap.json` entry, no `ATELIER.md` entry):
`src/mirai/surface_slide/` — `reference.py` (`SlideReference`), `tracer.py` (`trace`, launches, flags, `back_off`),
`curves.py` (`EdgeChain`), `slide.py` (`SurfaceSlide`, `SlideFrame`, `direct_frames`, `tree_frames`, `frame_jumps`);
the contract is the package docstring. NumPy only through `viewport.packed_geometry`; nothing imports `core`, a camera
or the GUI. Nothing in `src/` or `tests/` imports `experiments/`.

**Gate G1: green** [M] (container, NumPy 2.5.3). Oracle `experiments/surface_slide/tests/test_production_oracle.py`
(209 tests, ≈ 18 s) on all 76 scenarios; scenarios without a prototype transport (independent probes, which the report
ran with `project`) get the prototype's tree frames from their first vertex:

| Check | Result |
|---|---|
| Port with the prototype's tree frames injected vs `GeodesicPursuit("transport")`, every frame | **bit-identical** (max deviation 0 h; asserted ≤ 1e-12 h), same anchor triangles, same lagging rows, same wall stops; zero drag afterwards = start, bit for bit |
| Port with its own direct transport, 76 scenarios | 0 region jumps; step ratio ≤ 2 (2.00 on the cage loops); tracked deviation ≤ 1e-12 h; closure exactly 0 on all six loops; no `STUCK` / `MAXITER`; weight-0 rows untouched |
| Edge distortion direct vs tree, 47 soft / rigid scenarios | within 4 points everywhere (worst +1.6 points `D_hires_lip_down`, best −4.2 `D_cage_nose_to_cheek`) |
| Rigid patches (§3.2 table) | identical to the audit's direct column (sphere 3 / 8 edges 2.0 / 8.1 % and 12.7 / 41.8 %, cage cheek 8.0 / 19.6 %, forehead 3.0 / 7.9 %, brow 13.8 / 62.8 %, cylinder 0.05 / 0.11 %) |
| Neighbour direction jump, cage r = 0.15, polygon edges (nose tip / lid / lip) | tree 67.6 / 73.4 / 39.9°, direct **27.6 / 49.4 / 38.9°**; brow, nose side: direct ≤ tree |
| `EdgeChain` vs the prototype's `SeamCurve`, every cage seam vertex × 4 drags | same points (≤ 1e-15), plane coordinate exactly 0, same end stops |
| Seam rows in a slide (cage, seam = chain + barrier, drag across the plane) | seam rows x == 0 exactly, driven rows x > 0 in every frame |

**Production tests** (self-contained, generated sphere / cone / U / thin fin / sheets / tube, `tests/surface_slide_fixtures.py`):
`tests/test_surface_slide_core.py` (14: adjacency, read-only arrays, edge codes and refusals, exact unrolled geodesics on
the U incl. round the bend, boundary / barrier / capture stops, back-off strictly off the plane, blocked starts,
inconsistent winding, seam chain exactly on the plane, boundary loop, chain ends) and
`tests/test_surface_slide_slide.py` (18: zero drag bit-exact, function of the drag alone, weights / weight 0, step
≤ (1 + gain) × Δtangent and positions == anchors on the surface every frame, transport continuity on a cone (tree > 90°,
direct < 25°), antipodal fallback on a narrow U ("down wall A" becomes "up wall B"), loop round an apex tears, is
limited and closes exactly, loop ending near zero catches up, `settle` lands exactly on the target, no skip through a
2 % fin, snap guard, degenerate-gap chase, barrier back-off, boundary rows along the rim (E5) vs blocked without the
chain, seam rows on the plane under a turning drag, capture flag, refusals). The snap-guard test fails with the guard
removed; the fin test passes either way (as `probe_thin`: 0 skips observed). Runs: the two files,
`experiments/surface_slide/tests` (70 prototype + 209 oracle), `tests/test_packed_geometry.py`: **330 passed**.

**Decisions made while building (DI), deviations from the handoff:**

1. **`update(delta)` takes a world 3-vector**, projected into the pivot's start tangent plane exactly as the prototype
   does (that is what keeps G1 bit-identical, and what the M1 mapping produces); `tangent_of(delta)` gives the 2D pivot
   coordinates of report §14.4 for display.
2. **Snap guard:** a row takes its target when the chord gap is within the budget *and* the target triangle shares a
   corner with the current one — or a chase over the chord lands next to the target. §3.7 item 2 said "not lagging and
   shares a vertex with the previous target's"; that would never let a lagging row catch up exactly, and would make a
   fast frame that crosses several triangles lag (G1 would no longer be bit-identical).
3. **Barrier back-off:** the stop is pulled towards the triangle's opposite corner, to 98 % of the way from that corner
   (`BARRIER_MAX_AMOUNT`, the Vertex Slide precedent). A convex combination, so always inside the triangle and strictly
   off the barrier edge; "along the incoming direction" can leave the triangle when the hit is near a corner. Cost:
   when a target first reaches the barrier it steps back by ≤ 2 % of that triangle (the pursuit limits it).
4. **Antipodal fallback** (`n_pivot · n_i < −0.5`): the rotation is composed along the shortest triangle-edge path,
   starting from the last vertex on the path that still has a direct rotation, only for those rows and their antipodal
   ancestors, batched by depth; the search stays inside the rows' triangles unless a path leaves them.
5. **Chain rows pursue in arc length** (1D), so the speed limit holds for seam and boundary rows too; a closed loop stops
   where it started, an end or branch flags `CHAIN_END`. Chains are passed by the caller (seam before boundary):
   `EdgeChain.boundary(reference)` is the E5 boundary chain; without it a boundary row keeps the prototype rule
   (blocked when pointing out) — that is how the oracle runs.
6. **Vertex normals:** the prototype's angle-weighted normals by default (G1 needs them), injectable
   (`vertex_normals=`). With flat evaluation (E1) they only steer launches, tangent planes and the transport; whether
   Phase 2 passes `PackedGeometry` normals is open there.
7. **`h`** (`edge_scale`, the unit of the 1e-12 / 1e-14 tolerances) defaults to the mean *triangle* edge; the oracle
   passes the prototype's polygon mean edge. Phase 2 should pass the polygon mean edge too.
8. **Flags** are `uint16`: `BOUNDARY 1, STUCK 2, BLOCKED 4, MAXITER 8, BARRIER 16, CAPTURE 32, CHAIN_END 64,
   LAGGING 128`; a frame carries target and chase flags. A blocked start on a capture border also gets `CAPTURE`
   (Phase 2 grows the capture there).

**Container costs** [M] (indicative only; P1–P8 are Phase 4, reference PC ≈ × 3): reference build on the 21.9k Gollum
triangles 45–53 ms, 907 bytes per vertex (P8 ≤ 1 KB); direct frames 0.26 ms for 1 125 rows, 40 ms for 10 276 rows
(717 of them antipodal: the Python Dijkstra of the fallback dominates; the first version spent 417 ms composing every
settled vertex, now only the paths needed); `update` 1 125 rows 2.7–3.1 ms median at a 2 h drag, 4.5–5.0 ms at 10 h
(max 8 ms); 10 276 rows 26–32 / 47–59 ms.

**Open for Phase 2** (unchanged scope): `plan_surface_slide` from a `core.Mesh` (VertexId ↔ row, weights, mask,
hidden faces as barriers), region capture with growth on `CAPTURE`, the symmetry driver rule (B3) and the mirrored
writes, refusals (straddling faces, bowtie vertices), the normal source and `h` (items 6–7).

### 13.2 Handoff: Phase 2 (plan, capture, symmetry)

Mode (M5): Production, extends `src/mirai/surface_slide/`; still no gesture, no binding (Phase 3). Read §3.1, §3.5,
§3.6, §7, §9 (row 2, gate G2), §13.1 and the package docstring; the Phase 1 API is the base, do not re-port.

**Build** `plan.py` (`plan_surface_slide(mesh, seeds, *, influence=None, mask=None, symmetry=None) -> SlidePlan`,
`SurfaceSlideRefused(ValueError)`, the message is the status line) and the capture from a `core.Mesh`:

- Weights from `soft_selection.compute_influence` / `symmetric.symmetric_influence` unchanged; `mask.mask_weights`
  (weight × (1 − mask)); pivot = the seed the gesture starts on. Precedent for planning and refusals:
  `topology/vertex_slide.py` (`plan_vertex_slide`, `VertexSlideRefused`, `vertex_slide_positions`).
- **Driver rule (B3):** drive the pivot's half plus the seam, whatever K-near says; every vertex on the other half is
  written as `symmetry.mirror_position` of its partner (`symmetry_coordination.SymmetryIndex`, `is_exact_plane`);
  weights pair-consistent. Refuse without a partner, on a non-exact plane.
- **Capture (B1, B2):** faces within a margin of the driven set, triangles from `viewport.derived.triangulate_mesh_face`
  (no second rule); `capture_edges` = the captured region's border, `barrier_edges` = the declared seam
  (`definition.seam_edges`) + edges of hidden faces (hidden faces not captured). On any `FLAG_CAPTURE` in a frame:
  grow the region (radius × 2), rebuild, replay the current drag. Gate: region capture == full capture bit for bit.
- Chains: `[seam chain, EdgeChain.boundary(ref)]` in that order (seam wins at a seam vertex on a boundary).
- Refusals: straddling faces (both sides, no seam vertex) and bowtie vertices in the driven region, no partner.
- Open from §13.1: pass `edge_scale` = mean polygon edge; decide the vertex-normal source (keep angle-weighted unless
  a measured reason says otherwise).

**Gate G2** (§9): Gollum cage (`scenes/Gollum_Head_01.mirai.json`) and `examples/meshes/head_basemesh.obj`: mirror
pairs bitwise exact, seam coordinate exactly 0, no `AMBIGUOUS` after a barrier stop, every driven vertex on the drawn
triangles of its face (≤ 1e-12 h), region capture == full capture bit for bit, `tests/mesh_invariants.py` after every
written frame, refusals tested. Runs: the new tests, `tests/test_surface_slide_*.py`, the G1 oracle,
`tests/test_packed_geometry.py`, and the tests of any `src/` module touched outside the package.

**Done means:** G2 green, an implementation note §13.3, no app wiring.

### 13.3 Implementation note — Phase 2 done (2026-11-15)

**Built** (Production, in `src/mirai/surface_slide/`; no app wiring, no binding, no `keymap.json` entry, no
`ATELIER.md` entry; nothing outside the package changed):

- `capture.py` — `MeshHalf` (the capturable part of a `core.Mesh` at the press: snapshot positions, side, eligible /
  straddling polygons, chain edges), `region_faces` / `all_faces`, `build_capture` → `SlideCapture` (reference, row ↔
  `VertexId`, triangle → polygon, chains, `complete`).
- `plan.py` — `plan_surface_slide(mesh, seeds, *, pivot, influence, mask, symmetry, hidden_faces) -> SlidePlan`,
  `SurfaceSlideRefused`; `SlideSession` (region capture, growth ×2 with replay, `update` / `settle` →
  `SlideStep(positions, flags, lagging, captures)`, positions incl. the exact mirrors).
- `curves.py` — `EdgeChain(stop_short=, amount=)` and `ends()`; without `stop_short` bit-identical to Phase 1 (G1).
- Package docstring: contract item 8 (driver rule, drawn half, walls, region == full).

**Gate G2: green** [M] (container, NumPy 2.5.3): `tests/test_surface_slide_plan.py`, 12 tests, ≈ 7 s. Each scenario
runs a region session and a full session side by side and writes every region frame into the mesh in one journal
change; checked on **every written frame**: region == full **bit for bit** (positions, flags, lagging count);
`assert_mesh_invariants`; every driven vertex on a triangle of `triangulate_mesh_face` of its own polygon at the press
(corner ids equal, barycentrics ≥ 0, plane distance ≤ 1e-12 h), never on a hidden polygon; mirror pairs bitwise
(`mirror_position` of the driver); every seam vertex of the mesh at x == 0 exactly; driven vertices strictly on the
driven half; **no `AMBIGUOUS`** and every press pair still paired with its partner (also in the frames after barrier
and chain stops); then zero drag = press bit for bit and the rollback = `export_state()` before.

| Scenario | Mesh | What it shows |
|---|---|---|
| cheek, Soft 0.15, 15 h into the seam | cage | `BARRIER` stops backed off, pairs intact |
| seam vertex, Soft 0.12, up and across | cage | seam row on the declared seam chain, plane pinned |
| neck rim vertex, Soft 0.06, 12 h to the seam and back | cage | E5 along the boundary, stops short of the seam (`CHAIN_END`) |
| seeds on both halves, pivot on −X | cage | B3: −X driven, the +X seed written as a mirror (K-near ignored) |
| polygons hidden in the drag direction | cage | hidden polygons are walls (`BARRIER`), never entered |
| cheek into the seam; seam vertex; no definition | head_basemesh | same on a closed quad mesh; without a definition x = 0 is no wall (crosses) |
| margin 1 h, 15 h + 5 h drag | cage | ≥ 3 captures, every growth replayed, result == full |

Plus: capture structure (driven half only, canonical order, seam edges barriers and chain, seam normals in the plane,
capture border present / absent), mask and weights, refusals (nothing selected, all masked, pivot not a seed, a
falloff vertex without partner, a seed without partner, a non-exact plane, a seam vertex whose polygons are hidden,
a straddling polygon, a bowtie), `EdgeChain.stop_short`.
Runs: the new file, `tests/test_surface_slide_core.py`, `tests/test_surface_slide_slide.py`,
`experiments/surface_slide/tests` (G1 oracle), `tests/test_packed_geometry.py`: **342 passed**.

**Found by the gate and fixed:** two rim rows walking to the seam both stopped at "98 % of the last edge" — the same
point, so their mirrors coincided too (`AMBIGUOUS`). Rule now: a chain walk covers at most 98 % of *its own* path to a
stop vertex, so rows stop at distinct points in their order along the chain.

**Decisions made while building (DI), deviations from §13.2:**

1. **Signature:** `pivot=` (default: the seed nearest to the seeds' centroid) and `hidden_faces=` (the resolved hidden
   polygons) added; `influence` is the `SoftSettings` (None / disabled = no falloff); `mask` is the effective mask the
   caller passes as for W/E/R (hidden vertices fully masked); `symmetry` an optional `SymmetryIndex`.
2. **Driver rule:** a pair carries the larger of its two weights (the symmetric field gives both the same); a pivot on
   the seam drives the seeds' side, or +normal when the seeds are on both or none (the `symmetric_influence`
   convention). A seam vertex on no captured seam edge (its driven-side polygons hidden) does not move; as pivot it
   refuses ("cannot slide").
3. **Straddling** = corners strictly on both sides. Refused only where such a polygon touches a weighted vertex;
   elsewhere it is not captured and its edges are walls. **Bowtie** is checked on the Core topology (all polygons,
   hidden ones too) of the driven vertices.
4. **Capture:** Dijkstra from the driven vertices over the corners of eligible polygons (straight-line steps across a
   polygon, closer to geodesic than edges only), first margin `CAPTURE_MARGIN` = 4 h, ×2 per growth; a chain
   component a driven vertex walks is captured whole (a chain walk never ends at the region border). Positions from
   the press snapshot through `triangulate_face` — the rule of `triangulate_mesh_face`, which would read the
   positions the gesture has already written.
5. **Growth replays** every `update` / `settle` since the last exact zero drag (the pursuit carries state); with the
   canonical order (polygons by id, triangles in triangulation order, rows by id) the larger capture reproduces the
   full capture's frames bit for bit. Residual order dependences, none observed: `SlideReference.degenerate` scales
   with the largest captured triangle (only above area 1), the antipodal fallback's whole-surface search when a path
   leaves the rows.
6. **`h`** (§13.1 item 7) = mean polygon edge of the polygons around the driven vertices: part of every capture, so
   region and full use the same `h`; not mesh-wide (O(region)).
7. **Vertex normals** (§13.1 item 6): angle-weighted kept (no measured reason to change); seam vertices: plane
   component removed — exactly the direction of the half ring plus its mirror image (the half ring alone tilts it).
8. **Chain stops (E3, E5):** the seam chain stops short of its ends, the boundary chain of its ends and of seam
   vertices (≤ 98 % of the own path). Seam positions are pinned to the plane coordinate when written (no −0.0).
9. Refusal texts English and `PROVISIONAL` like Vertex Slide; `SoftSymmetryRefusal` is passed on in the status line.

**Container costs** [M] (indicative; P1–P8 are Phase 4, reference PC ≈ × 3 [T]):

| Case | Plan | Capture + slide setup | Full capture | `update` median 2 h / 10 h | Growth frame |
|---|---|---|---|---|---|
| cage, Soft 0.15: 57 driven + 57 mirrored | 9–13 ms | 8–12 ms (520 of 809 half polygons) | 15–21 ms | 0.9 / 1.7 ms | 54–62 ms (replay) |
| 20k (no definition), 987 driven | 29 ms | 31 ms (1 570 polygons, 857 B / vertex) | 335 ms | 3.6 / 6.1 ms | — |
| 20k (no definition), 4 293 driven | 75 ms | 140 ms (5 306 polygons, 884 B / vertex) | 348 ms | 15 / 24 ms | — |

Region capture removes the full-mesh capture (B2: 31 ms instead of 335 ms at ≈ 1 000 driven vertices). Arm for
≈ 1 000 vertices ≈ 60 ms container ≈ 180 ms reference PC [T]: above P1 (100 ms); Phase 4 (the geodesic influence is
shared with Soft Move; the capture's per-polygon Python loop). A growth frame costs the replay of the drag so far:
measure in Phase 4; if it hitches, transplant the pursuit state into the larger capture instead (same triangles,
same barycentrics) rather than replaying.

**Observed:** `examples/meshes/gollum_20k.obj` has no exact mirror pair at all under X (21 875 `UNPAIRED`, OBJ
rounding), so a symmetric Surface Slide refuses there, as every symmetric tool; the Gollum cage scene is exact.

**Open for Phase 3** (unchanged scope): `SurfaceSlideGesture` in `controllers/gestures.py` around `SlideSession`
(create at the press, write `SlideStep.positions` through the journal, status line from the flags and `lagging`),
the M1 mapping at the drawn pivot depth, the morph-mix rule (E2: the plan already reads the base positions), the live
radius change (replan + replay), the binding (E6).

### 13.4 Handoff: Phase 3 (gesture)

Mode (M5): Production; wires the Phase 2 API into the gesture layer. Read §3.4, §3.5 (rows Soft, Topology, Morph mix,
Pose, Hidden / mask, Input), §9 (row 3, gate G3), §13.3 and the docstrings of `surface_slide/plan.py` and
`controllers/gestures.py` (`_SlideGesture`, `VertexSlideGesture`, `shown_shift`). `SlideSession` is the base, do not
re-plan or re-capture inside the gesture.

**Stop first (E6, §5.1):** ask Manu which key / mode starts Surface Slide. `G` and every modifier of `G` are taken
(Loop / Vertex Slide, the region keys). Until he answers: the command exists **without a default binding** — nothing in
`interaction/bindings.py`, nothing in `config/keymap.json`; tests bind a test key (`app.bindings.bind`, as
`tests/test_layer_gate.py`). His answer goes into `keymap.json` with `"set"` and his wording in the commit message
(CLAUDE.md, AD-013 addendum). G3 does not wait for it.

**Build:**

- **Command** `commands.SURFACE_SLIDE`: a hold command (`HOLD_COMMANDS`), classified **position-only** in
  `layer_declarations` (`_POSITION_ONLY_COMMANDS`; this also gives the posed refusal of AD-028 §7.1 through
  `edits_positions_or_topology`, and `test_every_command_constant_is_classified` demands it), in `GESTURE_REFUSES` like
  the other hold keys, not in `_TOPOLOGY_COMMANDS` (positions only; hidden faces are walls, not a refusal).
  `Application._transform_arm` routes it to `GestureController.arm_surface_slide`.
- **Arm** (`arm_surface_slide`, refusals at the press as `_arm_vertex_slide`): seeds = selection resolved to vertices
  (`resolve_selection_vertices`, edge / face selections too, §6), else the hovered vertex; pivot = the hovered vertex
  if it is a seed, else the plan's default. `plan_surface_slide(mesh, seeds, pivot=, influence=services.soft_settings,
  mask=services.mask_values(seeds), hidden_faces=...)`; a new `AppServices.hidden_faces()` (same pattern and reason
  line as `hidden_vertices`). `SurfaceSlideRefused` → `services.status(str(exc))`, no gesture. Create the
  `SlideSession` here, at the press (it captures from the press state). Arm status line: count, Soft / symmetry hint,
  "release KEY to commit".
- **Gesture** `SurfaceSlideGesture(_SlideGesture)` (journal from the first motion, release = one `MeshDeltaCommand`,
  Esc = `rollback_change`, cleanup inherited; `_write` takes `SlideStep.positions`). `step(dx, dy)`: sum the pixel drag
  since the press; **M1 mapping** (E4): `services.edit_camera.screen_delta_to_world(p, sum_dx, sum_dy, w, h)` once per
  motion with the *absolute* sum, `p` = the pivot's press position plus `shown_shift` (the drawn depth, §15) —
  linear in the pixels, so a sum that is exactly 0 gives the exact zero vector; a sum within 1e-9 px of 0 counts as 0
  (the Vertex Slide rule for float sums). `session.update(delta)` → `_write`. Shift precision as Move
  (`PRECISION_GAIN`, add the command to that tuple in `motion`). Constraint keys do nothing
  (`UNCONSTRAINED_GESTURES`).
- **Morph mix (E2):** the plan reads the base (`scene.mesh`), so it slides on the rest surface; only the mapping point
  is drawn (`shown_shift`). Mix 0 % or no target: `shown_shift` is None, identical to no morph. The target's
  *editing view* (AD-025 §15, H4): check what W/E/R do there and follow it; test it either way.
- **Soft live** (`soft_live`, `reweight`, wheel / flow keys as `SmoothGesture.reweight`): write `plan.origins` back,
  re-plan from the press with the new settings (same seeds and pivot), new `SlideSession`, one `update` with the
  current delta; a refusal keeps the old plan. Show the weights (`show_weights`) at arm and after a reweight.
- **Status line per frame** (`PROVISIONAL`): the drag length in `h`, and the flags summarised — rows stopped at a wall
  (`BOUNDARY | BARRIER`), at a chain end, still lagging (`SlideStep.lagging`); "region grew" is not shown.
- **Release (E7 default):** commit what is shown; no `settle` (verdict in the practical test). `settle` is not wired.

**Not in Phase 3:** performance work (Phase 4: P1 arm time, the growth-replay hitch, §13.3), the practical test
(Phase 5), the cursor mapping M2, Phong, a kept reference, any change to `surface_slide/` beyond what wiring needs
(if the gesture needs an API change, keep G2 green).

**Gate G3** (§9) in `tests/test_surface_slide_gesture.py` (headless `Application`, as `tests/test_symmetric_ops.py`
and `tests/test_vertex_slide.py`: `init_scene`, `set_viewport_size`, a bound test key, `key_press` / `pointer_motion` /
`key_release`):

- one History entry per gesture; Undo / Redo exact (`export_state()` equality); Esc after motion and a drag back to
  the press pixel both bit-exact; a press without motion: no entry, nothing written;
- a held gesture refuses Undo / Redo / topology / mode commands (`BEGUN_GESTURE_REFUSES`, `GESTURE_REFUSES`); a second
  hold key is refused;
- refusals at the press reach the status line and leave no session (nothing selected, masked, no partner, …);
- posed, bound edit mesh: refused (AD-028); object mode: refused;
- morph mix on `scenes/Gollum_Head_01_Morphs.mirai.json`: at 0 % the result equals the same gesture without a target
  bit for bit; at 100 % the base vertices stay on the base surface (the drawn triangles of the press base,
  ≤ 1e-12 h) and the pivot's screen motion is mapped at the drawn depth;
- under symmetry on the Gollum cage: after release the mesh is still `SymmetryState.VALID`, mirror pairs bitwise;
- Soft live radius during the gesture: weights change, still one History entry, Esc exact;
- hidden faces: never entered (anchors), the rest of the mesh unchanged.

Runs: the new file, `tests/test_surface_slide_*.py`, the G1 oracle, then **`pytest tests` fully** and the GL tests in
their own process (`xvfb-run -a python -m pytest tests/test_gl_*.py -q`, AGENTS.md §8a; the shared files
`gestures.py`, `application.py`, `layer_declarations.py`, `commands.py` change), `experiments/morph_lab/tests`, the
Knife oracle (`experiments/knife_oracle`, the triangulation is untouched — confirm).

**Done means:** G3 green; E6 asked (bound only if Manu answered); docs in the same commit — `docs/ATELIER.md` entry only
once it has a key (it is then visible), the gesture list of `AD-027-INTERACTION-LAYER-SESSION-SLOT.md`, `docs/research/README.md`; an implementation note §13.5.

### 13.5 Implementation note — Phase 3 done (2026-11-15)

**E6 answered** (Manu, chat 2026-11-15, asked before the build): **„J“** — hold `J` starts Surface Slide, its own key
beside `G`. Default in `interaction/bindings.py` and entry in `config/keymap.json` with `"set": "2026-11-15"`. Bare `J`
was the Morph Lab's jaw toggle (0° ↔ last angle; the lab refuses to start on a taken key, AD-013 H2-R1); asked,
Manu: „Das Morphlab wird eh ausgebaut, dort kann die Taste weg.“ — removed from `experiments/morph_lab` (key, command,
README; `Shift+J` = hinge stays, it is free in the app).

**Built** (Production; `src/mirai/surface_slide/` unchanged except its package docstring, so G1 / G2 untouched):

- `commands.SURFACE_SLIDE` (`"SurfaceSlide"`): in `HOLD_COMMANDS`, **position-only** in `layer_declarations` (posed
  refusal, AD-028 §7.1), in `TRANSFORM_COMMANDS` (dispatch through `_run_gesture`, the status labels, and — through
  `objects.COMPONENT_COMMANDS` — the refusal in mode `4`), in `UNCONSTRAINED_GESTURES` and in the Shift precision
  tuple of `GestureSession.motion`. Not in `_TOPOLOGY_COMMANDS` (hidden faces are walls, not a refusal).
- `Application._transform_arm` → `GestureController.arm_surface_slide`; `GestureController.surface_slide_plan`
  (`plan_surface_slide` with `services.soft_settings`, `mask_values(seeds)`, `hidden_faces()`).
- `SurfaceSlideGesture(_SlideGesture)` and `surface_slide_weights(plan)` in `controllers/gestures.py`;
  `AppServices.hidden_faces()` (as `hidden_vertices`). `_SlideGesture` takes the command (default `LOOP_SLIDE`) and
  records every vertex it wrote (`touched`), so Esc tells the viewport about all of them, also after a re-plan.
- HUD tool name „Surface Slide“.

**Gate G3: green** [M] (container): `tests/test_surface_slide_gesture.py`, 12 tests, ≈ 3 s, headless `Application` on
the Gollum cage and on `scenes/Gollum_Head_01_Morphs.mirai.json`, the default key `J`:

| Test | What it pins |
|---|---|
| one entry, Undo / Redo | one History entry, `export_state()` equal after Undo and Redo, `SymmetryState.VALID` and every mirror pair bitwise after release and after Redo, `tests/mesh_invariants.py` |
| Esc / drag back | Esc after motion and a drag back to the press pixel: `export_state()` bit-exact, no entry |
| press without motion | „Surface Slide: no change“, nothing written, no entry |
| held gesture | `W` / `G` refused (one gesture), Ctrl+Z / Ctrl+Y / `C` / `2` / `3` / `4` change nothing and the gesture stays |
| refusals at the press | nothing selected or hovered, all masked, a vertex off its mirror image: status line, no session |
| object mode, posed | `4`: refused, nothing written; posed rig with a bound mesh: „is posed“, then at rest it arms |
| mix 0 % | the gesture on the base at 0 % == the same gesture with the targets removed, every vertex bit for bit |
| mix 100 % (Jaw_Open) | the mapping point is the drawn pivot (≤ 1e-12), the world delta is the mapping at the drawn depth (and differs from the rest depth); every driven vertex on a drawn triangle of the **press base** (≤ 1e-12 h); the offsets bit-identical |
| target editing view (H4) | slides the view (the target shape), as W does; Undo restores the offsets |
| Soft live | wheel during the gesture: new weights, still one entry (Undo exact), Esc exact, symmetric frames |
| hidden faces | never entered (anchors checked every frame), rows stop at them („at a wall“), only plan vertices move |

Runs: the new file; `tests/test_surface_slide_*.py` with the G1 oracle (`experiments/surface_slide/tests`): **335 passed**; `pytest tests`
fully under `xvfb-run`: **7 086 passed, 8 skipped, 4 failed** — three tests used bare `J` as "the unbound key" or listed the
hold family (`test_input_binding`, `test_keymap_config` ×2: now `0` and `SURFACE_SLIDE`, then 124 passed), and
`tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring` fails the same way without this change (pre-existing, step
5: W in the fake window arms no gesture; not touched here); the GL tests in their own process: **194 passed**; `experiments/morph_lab/tests`
(after the J removal): **49 passed** — before it, the lab's binding check failed on `J` (3 failed, 27 errors: that is
how the conflict was found); the Knife oracle (`experiments/knife_oracle`): **351 passed**, the triangulation is untouched.

**Decisions made while building (DI), deviations from §13.4:**

1. **Hover fallback:** the vertices of the hovered element of the active mode (`element_vertices`, the W/E/R rule),
   not only a hovered vertex. **Pivot:** the hovered vertex when it is a seed *and* not fully masked, else the plan's
   default (a masked hovered seed would otherwise refuse the whole gesture).
2. **M1 mapping:** `edit_camera.screen_delta_to_world(anchor, Σdx, Σdy, w, h)` once per motion (object space, as every
   gesture), `anchor` = the pivot's press position plus `shown_shift`, fixed at the press. `|Σ| ≤ 1e-9 px` per axis
   (`SURFACE_SLIDE_ZERO_PX`) gives the exact zero vector, so `SlideSession` resets and writes the press state.
3. **Shift** scales the motion by `PRECISION_GAIN` as Move; a drag back while Shift changed is, as for Move, not
   bit-exact (the pixel sum is not 0).
4. **Soft live:** writes `plan.origins` back (inside the journal), re-plans from the press with the same seeds and
   pivot, a new `SlideSession` and **one** `update` with the current delta (no replay of the drag history; rows may
   lag after a step, the pursuit closes in on the next motions). A refusal keeps the old plan and re-writes what it
   showed. The weights shown: driven vertices and, for mirrored ones, their driver's weight.
5. **„In `GESTURE_REFUSES` like the other hold keys“** read as: the same path as the other hold keys — none of them is
   a member of `GESTURE_REFUSES`; a second hold key is refused by `_transform_arm` (one gesture in the slot), which
   holds for `J` too (tested with `W` and `G`).
6. **Target editing view (H4):** W/E/R edit the view's mesh (the target shape); Surface Slide does the same — the plan
   reads the edit mesh, which is the view, and `shown_shift` is None there. Tested.
7. **Status line** (`PROVISIONAL`): arm „Surface Slide: N vertices [(Soft: wheel = radius)] [(symmetric)] - move the
   mouse, release J to commit“ (N counts the mirrored vertices); per frame „Surface Slide: 2.4 h · k at a wall · k at
   a chain end · k lagging“ (the drag's tangent length in `h`; `BOUNDARY | BARRIER` = wall); the symmetric field's
   refusal text is passed on unchanged (German, from `soft_selection`).
8. Release commits what is shown (E7 default); `settle` is not wired.

**Container costs** [M] (indicative, measured while the full suite ran in parallel; P1–P8 are Phase 4): Gollum cage,
cheek, hold J — no Soft (1 driven + 1 mirrored): arm 15 ms, motion median 0.5 ms (p95 1.0 ms); Soft 0.15 (60 driven
+ 60 mirrored): arm 25 ms, motion median 1.5 ms (p95 2.0 ms).

**Open** (unchanged scope): Phase 4 (P1 arm time at 1 000+ vertices, the growth-replay hitch, §13.3), Phase 5 practical
test (E4 cursor M1, E7 lag at release, E10 shape correction; how the key feels), the cursor mapping M2, Phong, a kept
reference.

## 14. Reproduce

```bash
python -m pytest experiments/surface_slide/tests -q
```

```bash
python -m pytest tests/test_surface_slide_core.py tests/test_surface_slide_slide.py tests/test_surface_slide_plan.py tests/test_surface_slide_gesture.py -q
```

```bash
python experiments/surface_slide/audit_2026-11-14/probe_symtri.py
```

The other probes (`probe_capture`, `probe_cursor`, `probe_thin`, `probe_holonomy`, `probe_direct`) run the same way;
see [their README](../../experiments/surface_slide/audit_2026-11-14/README.md).
