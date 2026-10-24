# Findings — Head Topology Walkthrough (D1 to D11)

**Status:** Discovery result, 2026-10-04. **Not artist-validated.** Artist verdict on the resulting workflow: **UNKNOWN** (not asked yet).
**Method:** [README.md](README.md). **Evidence:** [STEP_LOG.md](STEP_LOG.md) (every number below is in its detail section), `step_log.json`, `screenshots/`.
**Document under test:** [Character Head Topology — From Box to Deformation-Ready Face](../../docs/research/topology/Character%20Head%20Topology%20From%20Box%20to%20Deformation-Ready%20Face.md) (called "the document"). It was not edited.

Rules used here (FINDINGS practice): *Observation* = what was measured or what a tool did, mechanical. *Interpretation* = what the agent thinks it means, semantic, **unvalidated**.
Every deviation names the document claim it contradicts. Nothing was built to get past a gap.

Totals: 48 log lines (the document's numbered operations, D9 step 3 split into four rows with one corrective row, plus the cross-check row X1) — **held 32, deviated 9, blocked 7**.
Counts are per log line, and a line is `held` only if every measured check of its claim held.

---

## A. Deviations (the document's prediction did not hold)

### F-01 — The blockout has 36 quads, not 20 to 30  (D1.5)
- **Claim:** D1 *Result*: "about 20 to 30 quads".
- **Observation:** 2 x 2 x 2 cube = 24 quads; the muzzle extrusion of 2 faces adds 6; the neck extrusion of 2 faces adds 6: **36**.
- **Interpretation:** Each region-extrude of a 2-face patch costs +6 quads, so the figure depends on how many such extrusions D1 contains. Small; the order of magnitude is right.

### F-02 — One Extrude is not "forward-down"  (D1.3)
- **Claim:** D1 step 3: "Extrude the lower-front face pair forward-down once".
- **Observation:** The Playground `ExtrudeTool` moves the cap along the face normal only (forward). "Down" needed a second operation (a Move).
- **Interpretation:** "forward-down" is Extrude then Move. This matches `Extrude_als_Konstruktions-Paradigma_Research_V1.md` ("Extrude ist fast nie allein"). Not a topology problem.

### F-03 — The front has 10 vertical steps, not 9 rows  (D2.2, consequence in D7.2)
- **Claim:** Section C face budget "4 columns x 9 rows per half" and D2 step 2 (five upper rows, four muzzle/jaw rows).
- **Observation:** After D1.3 the extruded muzzle leaves a horizontal **shelf** quad strip between the upper front (5 rows) and the muzzle cap (4 rows). Along the seam: 5 + 1 + 4 = **10** vertical steps. The face has 72 front quads (8 x 9), +8 shelf quads: inside the "70 to 80" claim.
- **Interpretation:** The shelf is a product of D1.3's extrusion and is not in the budget. It also means the muzzle is made twice: once as a mass in D1.3 and again as a 6 x 4 region in D3. The document does not say how the two relate.

### F-04 — The cheekbone pole pair is two edges apart, not one  (D7.2)
- **Claim:** D7 step 2: "the eye's lower-outer E-pole and the muzzle's upper-outer E-pole sit one edge apart on the same column."
- **Observation:** Both poles exist, valence 5, both on the column x = 0.6375 (eye at y = 0.4, muzzle corner at y = 0.2). Shortest path along edges: **2** (through the shelf, F-03).
- **Interpretation:** Same cause as F-03. The "same column" part held.

### F-05 — "About 10 poles per half" counts only E-poles, and misses the blockout's  (D7.1, X1)
- **Claim:** D7 step 1 "Expect about 10 poles per half: 4 eye, 2 muzzle, 2 nose, 2 mouth"; Summary thesis 2 ("an E-pole at each patch corner").
- **Observation (after D6, feature caps closed, per half x>0):** 28 poles = 12 E + 16 N. E by origin: eye 4, muzzle 2, nose 2, mouth 2, **blockout (D1) 2**. N by origin: blockout 6, eye 4, muzzle 2, nose 2, mouth 2.
  With both eye caps and the mouth cap removed on a copy: 22 poles = 12 E + 10 N.
  Final cage (ears, nostrils added): 39 poles per half = 16 E + 23 N, plus 2 on the seam.
- **Interpretation:** The document's 10 is an E-pole budget for the features. Every region extrude or inset also leaves four valence-3 corners on its cap (see F-06), and the box blockout brings its own corner poles. The muzzle and nose caps are never opened, so their N-poles stay. Counting every vertex with valence other than 4 gives 2.8x the document's number at D7 and 3.9x at the end.

### F-06 — "No new poles" is literally false for the inset steps  (D5.3 to D5.5, D6.3 to D6.5; step verdicts stay *held*)
- **Claim:** D5 steps 3 and 4 "No new poles."; D6 steps 3 and 4 (implied).
- **Observation:** Each inset adds 4 valence-3 vertices per patch and removes the previous 4: 8 added / 8 removed for the two eyes, 4 / 4 for the mouth. **E-poles: 0 added; pole count per eye: constant (4 E + 4 N).**
- **Interpretation:** The document's own D intro predicts this ("inner corners become N-poles until the centre is opened or inset again"), so the *prediction* holds and only the wording of D5 steps 3 to 4 does not. The step verdicts therefore stay *held*; the wording gap is recorded here.

### F-07 — Loop Slide cannot move a loop that passes through a pole  (D7.4, D9.1)
- **Claim:** D7 step 4 "Slide the cheekbone row to the zygomatic line; do not cut."; D9 step 1 "Slide the bottom muzzle-wall row to the jaw line".
- **Observation:** Edge Loop selection stops at poles: the loop through the centre at y = 0.4 has 2 edges (open); the shelf-edge loop at y = 0.2 has 8 edges (open); the muzzle base row at y = -0.7 has 6 edges (open). Loop Slide requires closed loops (`LoopSlideError`: "kein eindeutiger Loop-Walk möglich"). Slides that **did** work: 4/4 global loops in D2.3 (before any pole existed), both orbit rings in D8.2, a pole-free ring around the muzzle wall in D9.1.
- **Interpretation:** In this app, "slide, never cut" as a repair strategy is available only on pole-free loops. Every row that touches an eye or muzzle corner pole is effectively fixed once the feature ring exists. In practice every slide has to happen before the ring that creates the pole (D2.3 does this), not after.

### F-08 — The D2 grid has no side grid for the ear; two global loops had to be added  (D9.3a, D9.3b)
- **Claim:** D9 step 3 "select a 2 x 2 patch on the side of the skull"; D2 "these are the last global loops"; section B principle 7, section E gate 1.
- **Observation:** After D2 the side of the head has 2 depth columns (z centres -0.5 and 0.5). A 2 x 2 patch would cover half the head's depth. **Corrective step D9.3b:** two coronal loops (z = -0.5, z = 0.5) added with Loop Insert; they run around the whole head: 458 -> 530 quads (+72), after all features exist.
- **Interpretation:** The face budget (section C table) has rows and columns for the front only. The ear needs a depth subdivision decided at D2. Not a tool problem.

### F-09 — Nostril insets create valence-6 vertices, two on the seam  (D10.3)
- **Claim:** D10 step 3 "select the nose underside face per half, inset, extrude up into the nose"; section B principle 8 / Summary ("no poles at the centre"; poles placed on purpose).
- **Observation:** The nose extrusion has 2 underside faces (one per half) that share the seam edge. Inset one after the other: 4 vertices of **valence 6** (2 on the seam at x = 0, 2 at x = ±0.187) and 8 valence-3 corners. Total after D10: 4 valence-6 vertices.
- **Interpretation:** Two separate regions that touch along the seam cannot get a gap by inset alone. A septum needs either one region inset (a single nostril ring) or a loop cut first. The document does not cover this case.

### F-10 — The finished cage has 674 quads and subdivides to 2,696, outside the document's ranges  (X1)
- **Claim:** Section C: "the cage lands near 300 to 500 quads for head and neck, which subdivides once into a working mesh of about 1,200 to 2,000 quads".
- **Observation:** 674 quads (head, neck, both ears, nostrils; eye and mouth caps still closed); one Catmull-Clark step on an all-quad cage is exactly 4 x 674 = 2,696.
- **Interpretation:** The grid of D2 alone is 254 quads (neck and back included); the global loops spend most of the budget before any feature exists (F-08 adds 72 more). Largest single contributors were not measured.

### F-11 — Lids and lips carry poles until the caps are opened  (X1; resolved only with a blocked capability)
- **Claim:** Task check "no poles on lids, canthi, lips, commissure"; D5 result "none on the lids or canthi"; D6 result "none at the commissure".
- **Observation:** Canthi and commissure: regular (valence 4 at every step). With the eye and mouth caps closed (the state this walkthrough could produce): **8 N-poles on the eye rings, 4 on the mouth rings**. On a copy with the caps removed (core `remove_face`, probe only): **0 and 0**.
- **Interpretation:** The prediction holds only after the "delete the cap" step, which no existing tool can do (G-01).

### F-12 — Blockout box corners remain in the finished cage  (X1)
- **Observation:** The cube's 8 corners are valence-3 vertices (D1.1). In the finished cage 6 N + 2 E per half still originate from the blockout (top corners, muzzle ledge ends, neck end).
- **Interpretation:** The document does not place these. The top corners sit on the cranium (low deformation); the others have not been judged.

---

## B. Capability gaps (steps `blocked`; nothing was built)

| ID | Missing capability | Steps blocked | Effect |
|---|---|---|---|
| G-01 | **Delete faces / open a hole** | D5.6, D6.6 (second half) | The eye and mouth caps cannot be removed; F-11 follows. The prediction was checked on a throw-away copy using core `Mesh.remove_face`: 8 E-poles / 0 N for both eyes, hole border valence 3. |
| G-02 | **Vertex valence display / select by valence** | D7.1 | Pole counts in this walkthrough come from the measurement script, not from a Playground tool. |
| G-03 | **Spin edge** | D7.3 | The document's pole-moving repair is unavailable. Collapse, Split, Connect exist and are not equivalent. |
| G-04 | **Subdivision applied to the control mesh** | D11.1 | The Subdivision Lab shows a derived surface only (its own README: D1). Preview on a probe copy: 16 / 16 / 24 hole borders, 68 interior extraordinary vertices before and after: the document's numbers (16, 24, poles stay) hold in the preview. |
| G-05 | **Seam / symmetry read-out in the Playground** | D2.4 | Measured by script instead: 26 seam vertices, 0 edges cross the plane x = 0. |
| G-06 | **Hinge / jaw reference** | D9.4 | "Away from the jaw hinge" cannot be judged mechanically. |
| — | Not blocked, but missing as single tools | 14 steps | **No Inset** (see Q-2) and no single "forward-down" extrude (F-02). |

Which gap blocks the most steps (Q-1): **G-01 (2 steps)**; G-02 to G-06 one step each. The missing Inset affects the most steps (14 of 48), but each was done with a composite of existing tools.

---

## C. Predictions that held (observations, no interpretation needed)

- D1.1: 3 Loop Inserts turn the cube into 24 quads; closed manifold from there to the end (Euler characteristic 2, every edge has two faces, at every measured step).
- D2.1: 6 loops give 4 columns per half, with the seam on a vertex column (9 vertex columns; no edge crosses x = 0).
- D3.2: region extrude of the 6 x 4 muzzle patch gives one closed 20-edge ring and **exactly 4 E-poles, at the patch corners**; no pole on the seam.
- D4.2: nose patch ring is 6 edges; 4 E-poles at its corners.
- D5.2: eye patch ring is 8 edges; **4 E-poles per eye exactly on the patch corners**; canthi (mid-side vertices) regular.
- D6.2: mouth patch ring is 12 edges; **4 E-poles (2 per half) on the patch corners**; commissure regular.
- D8.3 / D11.2: one loop inserted through a feature's concentric annulus stays inside it (8 new vertices per eye, 12 for the mouth; no existing vertex moved, pole count unchanged).
- D11.1 (preview): eye hole borders 16, mouth 24 after one level.
- Section C face budget: 72 front quads before features, inside "roughly 70 to 80".

---

## D. Spike result (screenshots)

**Yes.** `xvfb-run -a -s "-screen 0 1280x800x24" python experiments/head_topology_walkthrough/run_walkthrough.py` renders every frame through the real `PlaygroundWindow` (Mesa llvmpipe, GL 4.5) and saves PNGs without any manual step. Requires `pyglet`, `numpy`, `Pillow`. Evidence: `screenshots/`.
- **Observation:** the existing `playground/_diag_screenshot.py` draws one frame and saves an all-black PNG here; the committed `playground/_diag_head_view.png` is also all black. The driver warms up with three `dispatch_events()` + `on_draw` rounds, rebuilds the VBOs, and then reads the buffer.
- **Interpretation:** the script's single-frame capture is the likely cause; not changed (outside the allowed files).

---

## E. Open questions (reported, not resolved)

- **Q-1 Which missing capability blocks the most steps?** See section B: G-01 delete faces (2), the others 1 each; the missing Inset touches 14 steps but is emulated.
- **Q-2 Does "inset puts poles on the diagonals" hold in this app's inset?** **There is no Inset tool.** The composite **Extrude with distance 0 + Scale about the cap centroid** (`Extrude_als_Konstruktions-Paradigma_Research_V1.md` calls it "E mit Distanz 0 → S (= Inset)") puts E-poles exactly on the patch corners (the "diagonals" of the patch) at the first inset of a patch (D5.2, D6.2, D9.3c): the claim holds for that composite (D10.3 is the exception, F-09); it is not tested for a real Inset operation (constant width, not scale-based). The scale-based version shrinks uniformly, so ring spacing depends on patch proportions.
- **Q-3 Is a larger finding a reason to revisit the research document? (Proposal only.)** Yes for F-05 (pole budget counts E only), F-03/F-04 (shelf and double muzzle), F-07 (slide only before poles exist), F-08 (side grid for the ear) and F-09 (nostril septum). The document should then separate "E-pole budget" from "all poles", and state the order "slides before rings". Decision belongs to the artist.

## F. Limits of this walkthrough

- Driven by script through the tool classes (`ExtrudeTool`, `LoopSlideTool`, `ScaleTool`, `RotateTool`, `loop_insert`, `MoveOperation`), **not** through mouse and keyboard events; selection by position stands in for clicking. Whether the same steps are discoverable in the UI is untested.
- Symmetry done by hand: every one-sided operation was repeated mirrored (checked after each: `symmetric = True` at every measured step).
- The head is a crude box blockout. It tests topology predictions, not anatomy; "silhouette right" (D1) was not judged.
- Tool distances and factors (inset 0.72, 0.8 etc.) are the script's choices, not artist values.
- `Subdivision Lab` and the core `remove_face` were used only on copies (probe) and are marked as such in the log.
