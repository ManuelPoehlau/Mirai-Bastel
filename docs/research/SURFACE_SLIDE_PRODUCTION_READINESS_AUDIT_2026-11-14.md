# Surface Slide — Production Readiness Audit (2026-11-14)

**Status:** audit, English with a German summary. **No decision, no Production change.** It reviews the research
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
| **0 — Decisions** | E1, E2, E3, E5 answered; this audit's B1–B3 specs accepted; E6 when Phase 3 starts | Manu's answers recorded in this file |
| **1 — Pure core** | Port `reference`, `tracer`, `curves`, pursuit to `src/mirai/surface_slide/` on index arrays; transport per §3.2 | **G1**: on the report's 76 scenarios the port matches the prototype (oracle, like `knife_oracle`) to ≤ 1e-12 h for every geodesic candidate kept; prototype claims re-asserted (0 region jumps, step ratio ≤ 2, exact zero restore, weight 0 untouched, tracked deviation ≤ 1e-12 h); new tests: thin fin, boundary hit, near-zero loop, chase degenerate gap, transport jump metric (direct vs tree), antipodal normals |
| **2 — Plan, capture, symmetry** | `plan_surface_slide`, region capture from `core.Mesh` with `triangulate_mesh_face`, seam / boundary chains, barrier back-off, refusals | **G2**: on the Gollum cage and `examples/meshes/head_basemesh.obj`: mirror pairs bitwise exact, seam coordinate exactly 0, no `AMBIGUOUS` after a barrier stop, every driven vertex on the *drawn* triangles of its face (≤ 1e-12 h), region capture == full capture bit for bit, `tests/mesh_invariants.py` after every gesture, refusals tested |
| **3 — Gesture** | `SurfaceSlideGesture`, M1 mapping at the drawn depth, morph-mix rule (E2, tested on `scenes/Gollum_Head_01_Morphs.mirai.json`), binding (E6) | **G3**: one history entry; Undo / Redo exact; Esc and zero drag bit-exact (`export_state` equality); held-gesture refusals; posed refusal; mix 0 % ≡ no target; `pytest tests` fully and GL tests in their own process (AGENTS.md §8a), `experiments/morph_lab/tests`, the Knife oracle (shared triangulation untouched) |
| **4 — Performance** | Optimisations 1–3, probe | **G4**: container proxies of P1–P8; then a reference-PC run by Manu against P1–P8 |
| **5 — Practical test** | Short German test for Manu: cheek, brow, lid rim, lip, nose; with and without symmetry; soft radii; at 0 % and 100 % mix | **G5**: Manu's verdicts on E4, E7, E10 recorded; keymap entry only after his explicit approval |
| 6 — V1.1 (optional) | Phong / kept reference / cursor M2 / shape correction, each only on a recorded need | per item |

---

## 10. Open-problem register

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

## 12. Reproduce

```bash
python -m pytest experiments/surface_slide/tests -q
```

```bash
python experiments/surface_slide/audit_2026-11-14/probe_symtri.py
```

The other probes (`probe_capture`, `probe_cursor`, `probe_thin`, `probe_holonomy`, `probe_direct`) run the same way;
see [their README](../../experiments/surface_slide/audit_2026-11-14/README.md).
