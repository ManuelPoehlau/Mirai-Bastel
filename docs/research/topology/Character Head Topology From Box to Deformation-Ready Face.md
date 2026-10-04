# Character Head Topology: From Box to Deformation-Ready Face

Oct 3, 2026 · @Manu

## Summary

Fiddling is rarely a tool problem. It comes from making topological commitments in the wrong order: either too late (features carved out of a grid with global cuts) or too early (secondary form pushed into vertices before the loop network exists). Experienced modelers treat facial topology as a handful of planned decisions, and everything between those decisions as moves, not cuts.

Five theses run through this document:

- **Circumferential count is structural; concentric count is cheap.** How many edges run *around* the eye or mouth is decided once, early, because every radial edge travels outward into neighbouring regions. How many *rings* surround a feature can be added at any time, locally.
- **Region inset and region extrude are the same topological operation.** Both wrap a selected patch in a new closed ring and put an E-pole at each patch corner. An expert chooses the patch so those poles land where they are wanted. This single decision replaces most later repair.
- **Poles are placed, not discovered.** Every change of flow direction costs a pole. Experts budget them and park them in low-deformation zones (temple, cheekbone, jaw angle, ear root).
- **Professionals work hybrid.** Form-first at very low density for proportion; topology-first at one mid-stage commitment point; form-first again once the network is fixed.
- **For Mirai, the leverage is in intent-level operations and previews**, not in more primitive tools: "wrap this feature in a ring", "show me where this cut will travel", "walk this pole one step".

Sections A and the Sources list are researched from public material. Everything about operation sequences is reasoned from established subdivision-modeling practice and is labelled as such; no Weta procedure at that level of detail is publicly documented.

## A. Historical case study: what the public record supports

The public record supports methodology, not geometry. It documents how the face was built and tested, but no reliable source publishes the base mesh, its polygon count or the operation order. The findings below are the ones a methodology can rest on.

| Finding | Source | Confidence | Generalizable lesson |
| --- | --- | --- | --- |
| The head was built in Mirai starting from a cube, lined up against scan data of a physical maquette. | [AWN, Singer 2003](https://www.awn.com/animationworld/two-towers-face-face-gollum) | High (Raitt quoted) | Box modeling *to a fixed reference volume*. Form was largely given, so modeling effort went into topology and movement, not invention. |
| Design and topology were iterated together: the sculptor sat at the modeler's desk, they pulled the model into brows-up and smile, then the clay was revised. | AWN, Singer 2003 | High | Deformation was tested during design, not after. Topology was validated by posing at low density. |
| The first-film face followed a Weta Workshop model whose edge flow did not follow muscle structure in an animatable way; Raitt reworked the edge flow months before delivery. | [AWN, Schleifer 2004](https://www.awn.com/vfxworld/gollum-and-me-my-precious-experience) | High (caption with comparison images) | A topology that captures a static sculpture is not a topology for a moving face. Even at Weta this cost one full retopology. |
| Skin draped directly over bone with no muscle mass looked as if it moved for no reason once pulled around digitally. | AWN, Singer 2003 | High | Topology and form must imply the moving masses underneath. Loops describe what moves, not only what is visible. |
| Expressions were built as a network of combination shapes ("frown", "brows up", and "brows up + frown" as its own sculpt) driven by about 64 FACS-style controls. | AWN, Singer 2003 | High | The base mesh had to support hundreds of shapes sculpted by several artists. Predictable, evenly spaced loops mattered more than a minimal vertex count. |
| Shape count: 875 combination shapes (Singer), more than 800 sculpts (Schleifer), 946 targets (cited in the [blendshape literature](https://graphics.cs.uh.edu/wp-content/papers/2014/2014-EG-blendshape_STAR.pdf)). | Three sources | Medium (counting methods differ) | Order of magnitude is what matters: every vertex in the cage is placed hundreds of times. Vertex economy is labour economy. |
| Shape work was split by region: lip sputters and cheek puffs, jaw and skull motion on mouth opening, eye squints with sticky lips, each by a different artist, then merged by Raitt. | AWN, Singer 2003 | High | The topology had zones with clear boundaries, so regions could be sculpted independently and recombined. That is the "network" view of section B. |
| Mirai uses a winged-edge structure and descends from Symbolics S-Geometry; Raitt had been its product manager before Weta. | [Wikipedia: Mirai](<https://en.wikipedia.org/wiki/Mirai_(software)>), AWN 2003 | High | The tool was built around adjacency (loops, rings, neighbours). Loop-aware operations were native, not bolted on. |
| "Edge loop" as a modeling term is attributed to Raitt, in a 1999 3D Design article on digital sculpting. | [Wikipedia: Edge loop](https://en.wikipedia.org/wiki/Edge_loop) | Medium (secondary source) | The vocabulary itself came from this workflow: loops following orbicularis oculi and oris. |
| Wings 3D was explicitly inspired by Nendo and Mirai; its core vocabulary is loop and ring select, connect, cut-into-N, extrude, bridge. | [Wings 3D](https://wings3d.com/) | High | Wings is the best surviving, inspectable proxy for the Mirai interaction model. |

**Not reliably knowable from public material:** the exact wireframe, pole positions, polygon counts and operation order of the Gollum face. Leaked or fan-traced wireframes should not be treated as evidence. Sections C to G are therefore derived from general expert practice, checked against the principles above, and applied only to an original design.

The single most useful historical lesson: the expensive event in the record is the late edge-flow rework. The methodology below is designed to make that rework unnecessary by committing the flow at the right moment.

## B. General topology principles

Ten principles, each stated as a planning rule rather than a description.

1. **Loops describe what moves; density describes what is static.** Orbicularis oculi, orbicularis oris, the nasolabial fold and the jaw hinge get loops. Bony ridges, static wrinkles and asymmetric scars get vertex position or later sculpt detail, never their own loops.
2. **A closed ring is a locality contract.** Once a feature is wrapped in a closed ring, every further ring inserted inside it stays inside it. A feature defined only by crossing grid lines has no such contract: every new cut travels across the head.
3. **Two counts per feature, with different costs.** The *circumferential* count (edges around the feature) is global: changing it adds radial edges that run outward through neighbours. The *concentric* count (rings around the feature) is local and can grow at any time. Decide the first early; postpone the second.
4. **Even sides put feature corners on regular vertices.** A rectangular patch with an even number of edges per side has a mid-vertex on each side. That is where eye corners and mouth corners must live. An odd side puts the corner on an edge or forces a cut through the feature later.
5. **Every flow turn costs poles.** Redirecting flow by 90 degrees costs an N-pole (valence 3) and an E-pole (valence 5), or two E-poles where a ring is wrapped around a patch. Poles are a budget, not a defect. Place them where the surface stretches least during expressions.
6. **Counts must reconcile at junctions.** Where the eye system, the muzzle system and the skull grid meet, edge counts must match or be absorbed by poles. Plan the counts on paper; do not discover the mismatch with the knife.
7. **The cage is the lightest mesh that holds the network.** Each extra cage vertex is placed once in the neutral and again in every shape. Density comes last and uniformly (global subdivision or concentric rings), never as scattered local cuts.
8. **Symmetry and the centre seam are decided on day one.** The mirror plane must pass through a vertex column at the philtrum, nose bridge and chin, so the mouth and nose patches have centre vertices. A face column on the midline creates a mismatch that only a full loop cut can fix.
9. **N-gons are allowed as planned debt.** A temporary n-gon inside a region that will later be inset or extruded costs nothing. An n-gon left at a junction becomes a triangle or a pole in the wrong place.
10. **Regions are flow zones with borders.** The head is a network of a few systems (eye, muzzle and mouth, brow and forehead, jaw and neck, ear). Flow is continuous *inside* a system; poles and terminations live on the *borders* between systems.

**Where flow must be continuous, and where it may terminate:**

| Connection | Must flow continuously? | Why | Where it may terminate or redirect |
| --- | --- | --- | --- |
| Lip edge to outer mouth rings | Yes, closed rings | Commissure, lip roll and pucker all stretch around the mouth | Never at the lips or mouth corner |
| Lid edge to orbit rim | Yes, closed rings | Blink, squint and lid fold | Never at the lid or canthi |
| Mouth system to cheek | Partly: the outer muzzle ring is continuous; cheek flow merges into it | Smile pushes cheek mass upward along this border | Poles at the upper outer muzzle corner, on the cheekbone |
| Eye system to brow and forehead | Brow rows should continue across the forehead | Brow raise creates horizontal folds over the whole forehead | Poles at the temple and above the outer brow |
| Eye system to cheek | Lower orbit ring meets cheek grid | Squint and smile push the lower lid upward | Lower outer orbit corner, on the cheekbone |
| Muzzle to jaw and neck | Jaw rows continue into the neck | Jaw opening stretches the whole under-jaw | Jaw angle below the ear, under the chin |
| Ear to skull | No | Ear is nearly rigid | Ring of poles at the ear root is safe |

## C. Box to character head: the workflow

The workflow has nine stages, but only stages 2 to 4 change the topology's structure. Everything before them is cheap form work at minimum density; everything after them is local or uniform.

0. **Read the design for motion (paper, about 15 minutes).** Paint over the front and side views: mark eye rings, mouth rings, the muzzle ring, brow rows and jaw rows. Mark intended pole sites with dots. This is the expert habit that most self-taught box modelers skip, and it is where most later cuts are saved.
1. **Volume blockout (box, about 20 to 60 faces in total).** Cranium, muzzle mass, jaw, neck. Subdivision preview on. No facial features. Goal: proportions and silhouette only.
2. **Face budget and grid (commitment point 1).** Insert the loops that give the front of the head the planned grid: the face budget below. These are the last *global* cuts of the project.
3. **Feature volumes (commitment point 2).** Extrude the muzzle from the face grid, then the nose from the muzzle. Each extrusion wraps its patch in a closed ring and places four corner poles.
4. **Feature rings (commitment point 3).** Inset the eye patches and the mouth patch. Open the eye and mouth holes. Now every feature has a closed ring and every planned pole exists.
5. **Secondary deformation rings (local).** Lid thickness, lid fold, lip roll and inner lip, mouth bag, nostril, ear. All are concentric insets or extrudes inside existing rings.
6. **Pose test at cage level.** Jaw open, smile, blink, brow raise, sneer, done with simple selections or a temporary jaw bone. Fix by sliding and spinning edges, not cutting.
7. **Density pass (uniform).** One global subdivision step applied to the cage, or concentric ring inserts inside features. No new routing.
8. **Form refinement.** Slide, relax with pinned feature boundaries, sculpt secondary forms. Topology is now frozen.

**Face budget for this workflow (one half, front of head, before features).** The point is not these exact numbers; the point is that the numbers are chosen before cutting.

| Zone | Columns (centre outward) | Rows | Why this count |
| --- | --- | --- | --- |
| Nose bridge and centre | 1 | all | Mirror plane runs along a vertex column, so mouth and nose patches get centre vertices |
| Eye patch | 2 | 2 | 2 x 2 gives an 8-edge ring with corners on mid-side vertices (canthi) and poles on the diagonals |
| Outer orbit and temple | 1 | 2 | Pole parking for the outer eye corners |
| Forehead and brow | 4 | 2 | Brow row continues across the forehead |
| Under-eye and cheekbone | 4 | 1 | Separates eye and muzzle systems; pole parking |
| Muzzle front | 3 | 4 | Nose row, two mouth rows, chin row; mouth patch 2 tall so the commissure lands on a mid-side vertex |
| Jaw side | 1 | 4 | Continues into the neck |

Result: about 4 columns x 9 rows per half on the front, roughly 70 to 80 quads across the full face before features. After features and secondary rings the cage lands near 300 to 500 quads for head and neck, which subdivides once into a working mesh of about 1,200 to 2,000 quads.

## D. Operation chains

One topological fact drives most of these chains: **on a regular quad grid, inserting a ring around a rectangular patch (by inset or extrude) turns each patch corner on the outer boundary into an E-pole, leaves every mid-side vertex regular, and makes the inner corners N-poles until the centre is opened or inset again.** So the expert does not ask "where do I cut?" but "which patch do I select, so that the four corner poles land where I want them?" All chains below assume symmetry on, with the mirror plane on a vertex column.

### D1. Volume blockout

**Goal:** proportions of cranium, muzzle mass, jaw and neck at the lowest density that reads under subdivision.

**Start:** a cube.

**Operations:**

1. Subdivide the cube into 2 x 2 x 2 (mirror leaves 1 column per half).
2. Shape the cranium by moving whole faces and edge loops, not vertices.
3. Extrude the lower-front face pair forward-down once: the muzzle and jaw mass.
4. Extrude the bottom-back faces down once: the neck.
5. Proportion check in front, side and three-quarter views with subdivision preview.

**Result:** about 20 to 30 quads. Silhouette right, no features.

**Why this sequence:** at this density, every move is a large proportion decision and costs nothing. Proportion errors found later cost every vertex in a region.

**Alternative:** start from a subdivided sphere. Faster silhouette, but the poles of a UV sphere or the eight corners of a quad sphere land in fixed places, often on the face. Inferior unless those poles are deliberately placed at temple and jaw angle.

**Common failure:** adding loops here to "get the eye in". **Recovery:** dissolve them; features come after the grid.

### D2. Face grid (commitment point 1)

**Goal:** give the front of the head exactly the planned face budget (section C): about 4 columns x 9 rows per half.

**Start:** blockout from D1.

**Operations:**

1. Insert vertical edge loops through the front until there are 4 columns per half. Each loop runs around the whole head: that is intended, and these are the last global loops.
2. Insert horizontal loops until rows are forehead, brow, eye x 2, cheekbone, then four rows on the muzzle and jaw mass.
3. Slide (not move) each new loop to its anatomical line: brow ridge, lower orbit, cheekbone, lip line.
4. Check that the mirror seam is a vertex column.

**Result:** a regular grid whose cells already coincide with the future feature patches.

**Why this sequence:** global loops are cheap *before* features exist, because nothing local is crossed yet. Every global loop added after features cuts through eye or mouth rings.

**Alternative:** add loops only where needed while building features. Inferior: each loop is added while it crosses an existing feature, which is exactly the cascade-cut failure (section H).

**Common failure:** odd columns across the eye zone. **Recovery:** one extra vertical loop now, before D3, costs one operation; after D5 it costs a ring rebuild.

### D3. Muzzle volume (commitment point 2)

**Goal:** create the elongated muzzle and, in the same operation, its enclosing nasolabial-to-jaw ring.

**Start:** grid from D2; muzzle patch = 3 columns per half x the 4 lower rows.

**Operations:**

1. Select the muzzle patch (6 x 4 faces across both halves).
2. Region-extrude forward, with 2 segments if the muzzle is long.
3. Scale the cap down slightly and tilt it; shape the walls with loop selection on the extrusion's rings.

**Result:** a closed ring around the muzzle base. Its two outer corner vertices per half become E-poles: upper one on the cheekbone, lower one at the jowl. The centre crossings stay regular.

**Why this sequence:** the artist intends "create the next anatomical volume", and the extrusion's side walls *are* the muzzle ring. One operation creates the volume, the ring and two well-placed poles. Doing it by cuts takes a loop cut, a second loop cut, a dissolve of the overshoot on the skull, and two pole repairs.

**Alternative:** pull the muzzle out of the grid by moving vertices. Volume appears, but there is no ring: the mouth must later be wrapped by loops that run over the skull.

**Common failure:** extruding too few rows, so the mouth cannot be two rows tall. **Recovery:** one ring insert across the muzzle cap and walls (local, since the muzzle ring now contains it).

### D4. Nose

**Goal:** nose volume on the muzzle top-front with a ring for the alar crease.

**Start:** muzzle cap; nose patch = 1 column per half on the top cap row.

**Operations:**

1. Select the 2 centre faces of the top cap row.
2. Region-extrude forward and up; shape the tip with the cap loop.
3. Leave the underside alone: nostrils are secondary (D10).

**Result:** a closed 6-edge ring around the nose base; four E-poles at its corners. The two lower ones sit on the alar base, a site where a crease is wanted anyway.

**Why here:** after the muzzle exists, the nose ring is contained by the muzzle ring, so nose refinements never reach the eyes.

**Alternative:** model the nose as part of the muzzle extrusion. Fewer operations, but the alar crease then needs a later loop that runs around the whole muzzle.

**Common failure:** nose patch too wide (2 columns per half), putting poles on the cheek side of the alar crease. **Recovery:** spin-edge walk of each pole one step inward.

### D5. Eye system (commitment point 3)

**Goal:** a closed eye ring system with clean canthi, poles on the orbit diagonals, and depth for a deep-set eye.

**Start:** 2 x 2 eye patch per side, on the eye rows.

**Operations:**

1. Select the 2 x 2 patch.
2. Inset once: the orbit-rim ring. Four E-poles appear on the patch corners: upper-inner (brow by nose bridge), upper-outer (temple side), lower-outer (cheekbone), lower-inner (nasal side). The canthi land on the left and right mid-side vertices, both regular.
3. Inset again: the lid-fold ring. No new poles.
4. Inset again: the lid-margin ring. No new poles.
5. Instead of deleting the centre, extrude the innermost 2 x 2 inward (into the skull) and scale it down: lid thickness and socket depth.
6. Delete the extruded cap. The hole is an 8-edge border; its corner vertices become regular border vertices.

**Result:** 8-edge circumferential count (16 after one subdivision), 3 concentric rings plus a thickness ring, 4 poles per eye, none on the lids or canthi.

**Why this sequence:** the 2 x 2 choice in D2 is what makes this work. Even sides give mid-side canthi; the inset puts poles on the diagonals, where the orbit is supported by bone. Outer-to-inner order means each ring is placed relative to the one outside it, so spacing is controlled by the inset amount, not by vertex pushing.

**Alternative A:** cut a hole, then extrude the border outward ring by ring. Same topology, but the outer rings are built last, so the poles appear wherever the remaining grid happens to be: usually needs two spins.

**Alternative B:** a 3-wide x 2-tall patch. A legitimate variant: 10-edge ring, canthi still on mid-side vertices because the sides carrying them are 2 edges long. Its cost is one more global column in D2, made before any feature exists. A 2-wide x 3-tall patch is the inferior one: its sides are odd, so the canthi land on edge midpoints and each eye needs a connect plus a pole relocation later.

**Common failure:** insetting with "individual faces" mode, creating four separate rings. **Recovery:** undo; it is not repairable economically.

**Deep-set eye note:** depth comes from step 5 and from pulling the upper orbit ring under the brow row. No extra loop is needed until the density pass.

### D6. Mouth system

**Goal:** closed orbicularis rings, a commissure on a regular vertex, lip roll and a mouth bag.

**Start:** muzzle cap; mouth patch = 2 columns per half x the 2 mouth rows (4 x 2 across both halves, 12-edge boundary).

**Operations:**

1. Select the 4 x 2 patch.
2. Inset: the outer orbicularis ring. E-poles on the four patch corners: upper-outer (below the nasolabial top) and lower-outer (above the chin). The commissure is the mid-vertex of each short side: regular.
3. Inset: the vermilion-border ring.
4. Inset: the lip-margin ring.
5. Extrude the innermost patch inward: lip thickness and roll.
6. Extrude inward again and scale down: start of the mouth bag. Delete the cap.

**Result:** 12-edge circumferential count (24 after one subdivision), three concentric rings, lip thickness, two poles per half, none at the commissure.

**Why this sequence:** the muzzle ring from D3 already contains the mouth, so every mouth ring is local. The 2-row height chosen in D2 is what puts the commissure on a mid-side vertex.

**Alternative:** a single horizontal cut for the lip line, then loops around it. Faster to start, but the outer loops cross the cheek and jaw, and the commissure ends on a 5-pole: the classic smile pinch.

**Common failure:** mouth patch one row tall, putting the commissure on a corner E-pole. **Recovery:** ring insert across the muzzle cap, then rebuild the mouth inset. About 4 operations, all local thanks to the muzzle ring.

### D7. Cheek network and count reconciliation

**Goal:** confirm that eye, muzzle and skull systems meet with matching counts and that all poles sit on borders.

**Start:** after D3 to D6.

**Operations:**

1. Display vertex valence (or select by valence 3 and 5). Expect about 10 poles per half: 4 eye, 2 muzzle, 2 nose, 2 mouth.
2. Check the cheekbone: the eye's lower-outer E-pole and the muzzle's upper-outer E-pole sit one edge apart on the same column. That pair is the classic cheekbone configuration and is left alone.
3. Check the nasal side: the eye's lower-inner pole sits on the cheekbone row next to the muzzle wall. If the design's tear trough must crease, keep it; if it must stay smooth, spin one edge to move the pole one step toward the nose bridge.
4. Slide the cheekbone row to the zygomatic line; do not cut.

**Result:** no new topology. Poles are confirmed on borders between systems.

**Why:** this is a check, not a build step. Experts do it because one spin now replaces a deformation fix after rigging.

**Common failure:** "fixing" a pole pair by cutting a loop between them. That loop travels across the whole face. **Recovery:** dissolve it; use spin or slide.

### D8. Brow and forehead

**Goal:** a prominent brow ridge and forehead rows that crease on brow raise.

**Start:** brow row and upper orbit ring from D5.

**Operations:**

1. Loop-select the brow row and move it forward and down over the upper orbit ring.
2. Slide the upper orbit ring under it to deepen the shadow line.
3. If the ridge needs a harder edge, insert one loop through the orbit-rim face ring during the density pass (D11). That face ring closes around the eye, so the new loop stays local.

**Result:** brow form from existing topology only.

**Why:** the brow is a static bony mass with a moving skin layer over it. Its form is position, its motion is the forehead rows. No new loop until density demands it.

**Common failure:** cutting a horizontal loop across the forehead for the ridge. It runs around the skull and through both temples. **Recovery:** dissolve; use the existing brow row.

### D9. Jaw, neck and ear

**Goal:** jaw rows continuous into the neck; ear attached by a local ring.

**Start:** neck extrusion from D1; skull side grid.

**Operations:**

1. Slide the bottom muzzle-wall row to the jaw line; it continues back to below the ear.
2. Extrude the neck bottom once more if length is needed.
3. Ear: select a 2 x 2 patch on the side of the skull (behind the jaw hinge). Inset once (ear-root ring), extrude out for the ear volume, inset the outer face for the helix rim, extrude in for the concha.
4. Place the ear-root poles toward the skull, away from the jaw hinge.

**Result:** a rigid ear with four poles at its root, in the least deforming area of the head.

**Why:** the ear is a separate system. Its ring keeps all ear detail local.

**Alternative:** model the ear separately and bridge it on. Better for a very complex ear; costs a count-matching step at the bridge.

**Common failure:** ear patch overlapping the jaw hinge. **Recovery:** move the patch before insetting; after insetting, spin the two lower-front poles back.

### D10. Secondary deformation rings

**Goal:** lid margins, lip roll, nostrils, inner mouth.

**Operations (each local):**

1. Lids: inset the lid-margin ring once more for a crisp margin under subdivision.
2. Lips: inset once on the vermilion border for the lip line.
3. Nostrils: select the nose underside face per half, inset, extrude up into the nose.
4. Mouth bag: extrude the inner border further back and close it.

**Why last:** each depends on a ring that exists. Done earlier, each would have needed its own surrounding cut.

### D11. Density pass

**Goal:** working density for shapes and sculpt.

**Operations:**

1. Freeze one level of subdivision on the cage (global, uniform).
2. If one region needs more, add concentric rings inside its feature ring only.

**Result:** eye 16 around, mouth 24 around; all poles remain where they were placed.

**Why:** the cage counts (8 and 12) were chosen as halves of the target counts. One global step reaches the targets without any routing. This is the payoff of the D2 decision.

## E. Topology decision points

There are two gates. Before gate 1, global loops are cheap because no feature exists yet. Between the gates, every structural decision is made through closed rings. After gate 2, the topology is frozen and corrections are moves, spins and slides.

&#91;embedded content: topology commitment phases · 3 phases, 2 gates\]

The middle phase is where the expert spends the most thought and the fewest operations.

| Decision | Phase | If made too early | If made too late |
| --- | --- | --- | --- |
| Mirror seam on a vertex column | Early | No cost | A full loop cut through every centre feature |
| Face budget (columns x rows) | Early | Grid fixed before proportions settle: a few slides | Global loops cross existing features: cascade cuts |
| Circumferential counts (eye, mouth) | Early | Rarely a problem | Radial loops run through cheek, brow and jaw |
| Feature volumes (muzzle, nose, ear) | Mid | Volume placed before proportions: must be moved as a block | Features carved with cuts; no enclosing ring |
| Corner pole positions | Mid | None, if the patch choice was planned | Pole walking by repeated spins; poles near lids or commissure |
| Concentric ring count | Mid to late | Dense cage, heavy form editing | Cheap at any time: local inserts |
| Secondary deformation rings (lid margin, lip roll) | Mid to late | Extra vertices to place in every proportion change | Local inserts; no penalty |
| Secondary form (wrinkles, lid crease shape, bony detail) | Late | Pushed into cage vertices, destroyed by the next ring insert, pushed again | No penalty |

## F. Topology economy

An efficient sequence is one whose topological consequences are known before each operation is executed. Operation count is a symptom; predictability is the cause. A chain of six predictable operations beats a chain of four that leaves a pole at the commissure.

**Working definition.** Economy = (topology-changing operations that the final mesh needs) divided by (all topology-changing operations performed), with two side conditions: no pole ends up in a no-go zone, and the next planned operation is still local.

**The look-ahead questions** an expert runs, mostly unconsciously, before every topology-changing operation:

1. Where does this end? A loop insert runs until it meets a pole or a border. If that is the back of the head, it is the wrong operation.
2. What poles does it create, and where do they land?
3. Which circumferential counts does it change?
4. Which later operations does it enable, and which does it make unnecessary?
5. Could a move (slide, spin, relax with pins) do this instead?

**Example ledger: one eye, from the same blockout.** The unplanned chain is a typical self-taught box-modeling path; the planned chain is D2 plus D5.

| Measure | Unplanned chain | Planned chain |
| --- | --- | --- |
| Steps | Horizontal loop cut, vertical loop cut, knife a diamond, delete, fill, round by vertex moves, cut for canthus, weld a triangle, dissolve a stray loop at the back of the head, spin a pole off the canthus | Select 2 x 2 patch, inset, inset, inset, extrude inward, delete cap |
| Topology-changing operations | about 9 | 5 |
| Corrective operations | about 4 | 0 |
| Global cuts after features exist | 3 | 0 (the grid loops were made before any feature) |
| Vertex placements to round the eye | every ring vertex, by hand | inset amounts plus one circularize or relax with pinned border |
| Poles on lids or canthi | likely | none by construction |

**Substitution patterns.** Each row replaces a corrective chain with one planned operation. These are the patterns most worth internalizing.

| Instead of | Use | What the artist actually wants |
| --- | --- | --- |
| Crossing loop cuts, then knife and weld to carve a feature | Region inset or region extrude | A closed ring around a feature |
| A loop cut to add density near a feature | A loop through the feature's own face ring | One more deformation ring, locally |
| Cut, then move each new vertex onto the surface | Insert with slide, or slide afterwards | A loop at an anatomical line, on the surface |
| Dissolve, then reconnect to turn flow | Spin edge (one operation per step) | Redirect flow or move a pole one step |
| More cuts to remove a triangle | Connect two triangles across a strip into quads, or collapse a short edge to turn the triangle into a pole at a safe site | Get rid of an irregularity without spreading it |
| Many small local cuts for density | One global subdivision of the cage | Uniform working density |
| Pushing cage vertices to sculpt secondary form | Wait for density, then sculpt | Detail that survives the next ring insert |
| Relaxing a whole region | Slide, or relax with feature borders pinned | Even spacing without losing designed loop positions |

The common thread: a corrective chain almost always reconstructs, step by step, the effect of one topological operation that was not chosen at the right moment.

## G. Pole strategy

Poles belong on the borders between flow systems, where the surface stretches least during expression. With the workflow above, a head carries about 10 planned poles per half before ears and neck, and every one of them was created by a deliberate patch choice.

**What each pole does.**

- **E-pole (valence 5):** where a ring wraps around a patch, or where two flows merge. Under subdivision it gives a slight star-shaped convergence; under stretch across it, it can pinch.
- **N-pole (valence 3):** where flow turns, often paired with an E-pole. Under subdivision it tends to a small flat spot; under compression it can dimple.
- **Pole pair (N + E, adjacent):** the standard cost of turning flow by one step. Moving the pair by spin edge moves the turn.
- **Pole chain:** several poles along one line, typically where a feature ring meets a grid. Acceptable along a natural crease or bony ridge; a problem if the chain crosses a fold that animates.

**Where poles may live.**

| Region | Typical pole | Safe? | Reason |
| --- | --- | --- | --- |
| Temple, outer orbit corner | E-pole from the eye ring | Safe | Thin skin over bone, little stretch; the classic parking spot |
| Cheekbone (zygoma) | E-poles from eye and muzzle rings, often a pair | Safe | Bony support; smile pushes mass *over* it rather than stretching it |
| Upper inner orbit, by the nose bridge | E-pole from the eye ring | Mostly safe | Some motion on frown; keep it off the brow's moving row |
| Lower inner orbit, tear trough | E-pole from the eye ring | Conditional | Squint and smile compress here; fine if a crease is wanted, otherwise spin one step toward the nose |
| Alar base, nose sides | E-poles from the nose ring | Safe | The alar crease is a wanted break in the surface |
| Upper end of nasolabial fold | E-pole from the mouth ring | Safe | The fold's top is a wanted crease |
| Middle of nasolabial fold | none | Avoid | Highest stretch during smile and sneer |
| Commissure (mouth corner) | none | Never | Every mouth shape passes through it |
| Lids and canthi | none | Never | Blink and squint need perfectly regular rings |
| Lip vermilion | none | Never | Lip roll and pucker reveal any irregularity |
| Chin, below the lower lip | E-poles from the mouth ring | Safe | Mentalis region moves as a block |
| Jowl, jaw angle below the ear | E-pole from the muzzle ring; neck-to-face turns | Safe | Low stretch; often hidden by the jaw silhouette |
| Forehead centre | none | Avoid | Brow raise creates long horizontal folds across it |
| Ear root | E-poles from the ear ring | Safe | Nearly rigid |

**Three planning rules.**

1. Count poles from the patch choices before any operation: four per inset or extruded rectangular patch, minus those on the mirror line. If the count looks wrong on paper, it will look wrong in the mesh.
2. Never fix a pole by cutting. Walk it with spin edge, one step per operation, toward the nearest safe zone in the table.
3. Test poles under deformation at cage density (stage 6). A pole that survives jaw open, smile and squint at cage level survives subdivision.

## H. Failure patterns: how box modeling degenerates into fiddling

Nearly every fiddling spiral starts with one of nine patterns, and most of them trace back to a decision skipped at gate 1 or gate 2.

| Pattern | Symptom | Root cause | Prevention | Recovery |
| --- | --- | --- | --- | --- |
| Cascade cut | A loop meant for the eye also runs through the mouth, neck and back of the head | Feature defined by crossing grid lines, no closed ring | Region inset or extrude per feature after gate 1 | Dissolve the loop outside the feature; terminate it with a pole pair in a safe zone |
| Odd-side feature | Canthus or commissure lands on an edge midpoint or a pole | Patch side carrying the corner has an odd edge count | Face budget with 2-edge sides at eye and mouth corners | One connect plus one spin per corner, or rebuild the inset |
| Pole drift | Poles creep toward lids and lips over many local fixes | Each fix moved a pole without a destination | Pole budget and safe-zone map before mid phase | Walk each pole back with spin edge |
| Detail before topology | Lid crease or wrinkles pushed into cage vertices, then destroyed by the next ring insert, then pushed again | Secondary form started before gate 2 | Cage holds primary form only | Accept loss; reshape after density pass |
| Triangle chasing | Removing one triangle creates another one nearby | Treating the triangle as local; it is a count mismatch | Reconcile counts at junctions on paper | Pair two triangles across a strip into quads, or turn one into a pole at a safe site |
| Count mismatch at a junction | Eye, muzzle and skull meet with leftover edges; n-gons or triangles at the cheek | Circumferential counts not planned against the grid | Choose cage counts as halves of target counts, and grid widths to match | Absorb the difference with one planned pole pair on the cheekbone |
| Over-dense cage | Every proportion change needs dozens of vertex moves | Density added before topology was final | Lightest cage that holds the network | Dissolve concentric rings that are not yet needed; they come back cheaply later |
| Fix before test | Loops added "for deformation" that the pose test would not have demanded | Guessing at deformation | Pose test at cage density (stage 6) | Dissolve the guessed loops; re-test |
| Asymmetry creep | Left and right halves no longer match topologically | Symmetry switched off for a "quick fix" | Topological symmetry from the first cube | Delete one half, re-mirror; then reapply intended asymmetry as shape only |

All nine share one mechanism: a local action whose global consequence was not visible at the moment of acting. That is also the most direct design target for a modeling tool.

## I. Alternative workflows compared

No workflow wins everywhere. Form-first is fastest to a likeness, topology-first is safest for deformation, and the hybrid is what most experienced box modelers converge on because it puts each kind of decision at its cheapest moment.

- **Workflow A, traditional box modeling (form-first):** cube to full silhouette and planes, then features carved in with cuts as they are needed.
- **Workflow B, topology-first (edge or poly-strip modeling):** eye and mouth rings built first as extruded edge strips or small ring patches, then connected and filled; volume grows around the network.
- **Workflow C, hybrid:** sections C and D of this document. Form-first to gate 1, topology-first between the gates (through region inset and extrude rather than strips), form-first again after gate 2.

| Criterion | A: Box, form-first | B: Topology-first | C: Hybrid |
| --- | --- | --- | --- |
| Operation count to a clean cage | High; many corrective operations | Medium; many small strip extrusions and fills | Lowest |
| Predictability | Low after features begin | High for features, low for overall volume | High at every stage |
| Topology quality | Depends on repair skill | Highest locally around features | High, planned |
| Ease of editing proportions | Excellent early, poor late | Poor: the network is built before the volume exists | Good: proportions are fixed before the network |
| Deformation quality | Variable; poles often drift | Very good | Very good |
| Risk of mismatch at junctions | High | Medium: rings built separately must be stitched | Low: rings are cut from one shared grid |
| Suitability for Mirai-style tools | Good for blockout only | Needs strong edge-extrude and fill tools | Best: relies on loop, ring, inset, extrude, spin, slide |
| Fit for an experienced traditional box modeler | Familiar, but this is where the fiddling lives | Unfamiliar, slow at first | Familiar operations in a new order; lowest relearning cost |

**When each works.**

- **A** works for heads that will not deform much (props, statues, background creatures), and for fast design exploration where the mesh will be retopologized anyway.
- **B** works when matching an existing scan or sculpt closely, where volume is given and only the network must be designed. It is close to modern retopology practice.
- **C** works for an original creature designed in the modeler, which will carry many shapes. It is also the closest match to the historical evidence in section A: start from a cube against a reference volume, test motion early, and make the edge flow follow what moves.

A fourth path, sculpt first and retopologize, is now the industry default for film characters. It is outside this document's scope, but every principle in sections B, E and G applies to the retopology step unchanged.

## J. Mirai implications

The greatest leverage is not a larger tool set but making each operation's global consequence visible before it is committed. The planned workflow in section D uses only about eight distinct operations; what makes it fast is that the artist knows where each ring, pole and count change will land.

**Capability ranking for efficient character box modeling.**

| Capability | Tier | Chains that depend on it | Artist intent it serves |
| --- | --- | --- | --- |
| Loop and ring selection (conservative: loops stop at poles) | Essential | D1, D2, D3, D8, D9 | "Treat this anatomical line as one thing" |
| Region inset and region extrude as one topological operation with two geometric variants | Essential | D3, D4, D5, D6, D9, D10 | "Wrap this feature in a ring" or "grow the next volume" |
| Ring insert (loop cut) with slide at creation | Essential | D2, D11, recoveries | "One more deformation ring here" |
| Slide (edge and vertex along the surface) | Essential | D2, D7, D8, D9 | "Put this loop on the anatomical line without changing topology" |
| Spin edge (rotate an edge within its two faces) | Essential | D7, pole recovery | "Turn flow here" or "move this pole one step" |
| Topological symmetry with a vertex-column seam | Essential | All | "Model one side once" |
| Dissolve edge and edge loop, with vertex cleanup | High | Recoveries in H | "This loop should not exist" |
| Connect (vertices or edge midpoints) | High | Count reconciliation, triangle pairing | "Route flow from here to there" |
| Relax with pinned borders | High | D5, D11 | "Even out spacing, keep the designed rings" |
| Bridge | Medium | Ear alternative, closing the mouth bag | "Join two open rings with matching counts" |
| Collapse and target weld | Medium | Triangle-to-pole recovery | "Remove this short edge" |
| Knife, bevel, circularize | Convenience | None in the planned chains | Useful, but mostly a substitute for a missing plan |

**Intent-level operations worth prototyping.** Each is a composition of existing primitives, but the artist states the intent, not the steps:

- **Wrap feature:** select a patch, get a closed ring with the four corner poles previewed before commit.
- **Add ring inside feature:** pick any edge of a feature's face ring; the new loop is guaranteed to stay within the enclosing ring.
- **Walk pole:** pick a pole and a direction; the tool performs the spin edge that moves it one step.
- **Terminate loop here:** end a flow at a chosen vertex by inserting the required pole pair.
- **Count check:** read out circumferential and concentric counts of a selected feature, and flag odd sides at marked feature corners.

**Interaction patterns with the most leverage.**

1. **Extent preview:** before a loop insert commits, show the complete path it will take. This alone prevents the cascade-cut pattern, the most common failure in section H.
2. **Valence overlay:** E-poles and N-poles drawn in two colours, optionally against a user-painted no-go zone (lids, lips, commissure).
3. **Repeat last operation with its parameters** (inset, inset, inset): operation chains become rhythm, not menu work.
4. **Undo as exploration:** because commitment points are few, an artist tries a patch choice, checks poles, and undoes. Snapshot-based undo already supports this at the cost of memory, not of correctness.

**Relevance to the existing core and rig experiments.** The core already has split, collapse and connect, plus conservative loop and ring traversal, with loop insert as the announced next step. Two observations follow from this research:

- Region inset and extrude can be composed from those primitives, but as a dedicated operation they carry clean parent information: every new ring vertex has exactly one parent on the patch boundary. That is the same information the rig experiment lacks today for split operations (no parent edge metadata). Feature-ring operations would make weight and morph inheritance unambiguous by construction.
- Concentric ring inserts inside a feature are the most rig-friendly topology edit possible: each new vertex lies between two existing rings, so weights and morph deltas interpolate between two known parents. If edits to a rigged head are restricted to that operation after gate 2, the hardest open design questions in the rig experiment (merge semantics) do not arise for the common case.

Open questions for the UX research phase on topology: whether "wrap feature" should be one operation with an inset or extrude toggle, or two operations; and whether the extent preview should appear on hover or only during a drag.

## K. Practice exercise: the Fen Warden

The exercise tests one claim: with a planned face budget and region-ring operations, an original creature head reaches a deformation-ready cage with zero corrective operations and no poles in no-go zones.

**Design (original).** A marsh-dwelling creature, calm and watchful. Human facial organization, scaled for a long, slightly downward-sloping muzzle. Heavy, continuous brow shelf. Small deep-set eyes in shadow. Wide, thin-lipped mouth that can smile broadly and snarl. High, hard cheekbones. Tall, narrow ears set back behind the jaw hinge, slightly drooping. Long neck that leans forward from the skull.

**Rules.**

1. Draw the loop plan and pole sites on a front and side sketch before opening the modeler.
2. Symmetry on from the first cube; seam on a vertex column.
3. No global loop after gate 1.
4. No vertex-level secondary form before gate 2.
5. Log every operation as one line: name, topology-changing or move, local or global, planned or corrective.

**Targets.**

| Measure | Target |
| --- | --- |
| Face budget before features (per half, front) | 4 columns x 9 rows |
| Eye circumferential count, cage / after one subdivision | 8 / 16 |
| Mouth circumferential count, cage / after one subdivision | 12 / 24 |
| Planned poles per half, face only | about 10 |
| Poles on lids, canthi, lips, commissure, mid-nasolabial | 0 |
| Triangles and n-gons in the final cage | 0 |
| Corrective operations | 0 (any above 3 means a commitment point was skipped) |
| Cage size, head and neck | about 300 to 500 quads |

**Checkpoints.**

- [ ] Gate 1: silhouette approved in three views; face grid matches the budget.
- [ ] After D3 to D6: valence overlay shows only the planned poles.
- [ ] Gate 2: every feature has a closed ring; counts match the targets.
- [ ] Pose test at cage density: jaw open, broad smile, snarl, blink, squint, brow raise, frown. No pinching at any pole.
- [ ] Density pass by one global subdivision; no new routing.

**Variations to run afterwards.** Model the same design three times, once per workflow (A, B, C in section I), and compare the three operation logs. The logs are the evidence: they show where each workflow spends corrective work, and they are directly usable as interaction data for the topology research in Mirai.

## Sources

Pages opened for this document:

- [The Two Towers: Face to Face With Gollum](https://www.awn.com/animationworld/two-towers-face-face-gollum), Greg Singer, Animation World Network, March 2003. Primary source for the cube start, the scan-alignment and sculptor loop, combination sculpting, the 875 shapes and 64 controls.
- [Gollum and Me: My Precious Experience](https://www.awn.com/vfxworld/gollum-and-me-my-precious-experience), Jason Schleifer, VFXWorld, January 2004. Source for the edge-flow rework and the more-than-800 sculpts figure.
- [Mirai (software)](<https://en.wikipedia.org/wiki/Mirai_(software)>), Wikipedia. Winged-edge structure, Lisp, S-Geometry lineage, use for the Gollum morph targets.
- [Edge loop](https://en.wikipedia.org/wiki/Edge_loop), Wikipedia. Attribution of the term to Bay Raitt (1999); loops following orbicularis oculi and oris.
- [Bay Raitt](https://en.wikipedia.org/wiki/Bay_Raitt), Wikipedia. Role as creature facial lead; later Mirai use for Team Fortress 2 face shapes.
- [Blendshape facial animation, Eurographics 2014 state of the art report](https://graphics.cs.uh.edu/wp-content/papers/2014/2014-EG-blendshape_STAR.pdf), Lewis et al. Source of the 946-target figure, cited there to Raitt 2004.
- [Wings 3D](https://wings3d.com/). Inspiration by Nendo and Mirai; winged-edge structure.

**Confidence note.** Section A is sourced. Sections B to K are reasoned from established subdivision-modeling practice and checked for topological correctness (pole placement under region inset and extrude on a regular quad grid); they are not documented Weta procedure. The face budget and target counts are one consistent plan, not industry standards.
