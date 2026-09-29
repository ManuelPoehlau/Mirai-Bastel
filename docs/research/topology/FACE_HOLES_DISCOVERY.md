# Face Holes — a closed shape inside a face: Discovery

**Status:** Discovery — Research Package (Type B), **no decision**. Fresh first impression; archive
unchanged before discussion (AGENTS.md §6). Possible later Type C gate (architecture).
**Date:** 2026-09-29
**Mode (M5):** Discovery
**Belongs to:** [`KNIFE_FACE_CUT_DISCOVERY.md`](KNIFE_FACE_CUT_DISCOVERY.md) §2 FC6 (closed loop inside a face) ·
`playground/experiments/knife_face/decision.md` (task 5, closed-shape stand-in) · ARCH-02
(`docs/architecture/ROADMAP.md`) · `docs/architecture/CORE_V1_FREEZE.md` §7
**Code examined:** `ccr-d8697d4f-6z4f4f` @ `3a7576e` (= Knife Face Cut Lab)
**Probe:** [`experiments/topology/face_holes_probe.py`](../../../experiments/topology/face_holes_probe.py)
(public Core API + existing read-only consumers; no Core change, no Lab change)

> This document answers Q1–Q5 of the Face Holes discovery brief. It makes no product decision and no
> Core decision and implements no option. Observation and interpretation are kept apart; every external
> claim carries an evidence tag. Face Cut content (Knife references, FC1–FC7, B2a/B2b/B2c) is **not**
> repeated here — see [`KNIFE_FACE_CUT_DISCOVERY.md`](KNIFE_FACE_CUT_DISCOVERY.md).

**Evidence tags**

| Tag | Meaning |
|---|---|
| `[SRC]` | Read in published source code or a published SDK/API header (not executed). For closed-source tools (Maya, 3ds Max) this is the public API header only, read from a third-party GitHub mirror. |
| `[DOC]` | Official documentation wording — **only as search-engine excerpts**. help.autodesk.com, download.autodesk.com, nevercenter.com, learn.foundry.com, silo.pub, dokumen.pub, daz3d.com and paulbourke.net are blocked by this environment's network policy; no page was read in full. Wording may be paraphrased by the excerpt. |
| `[ART]` | Artist statement (from the brief, or recorded in the repository). |
| `[CODE]` | Mirai code read at `3a7576e`. |
| `[PROBE]` | Output of `face_holes_probe.py`, run at `3a7576e`. |
| `[ASSUMED]` | Plausible, not verified. |
| `[UNKNOWN]` | Could not be established here. |

---

## 0. Trigger and History Awareness (M1)

**Observation** `[ART]` (Manu, Silo, 2026-09-28; the Artist's observation, not reproduced by us): after cutting a
closed triangle into a face, only the triangle's edges are visible; the surrounding ring is selectable as
**one** face; deleting the triangle or the ring leaves a hole; extruding the ring produces a recess with a
hole.

**Interpretation** (agent, from the brief, checked in Q1): Silo faces can have inner boundaries (holes).

**Mirai today** `[CODE]`: a face is one ordered boundary list of ≥ 3 vertices (`src/core/mesh.py:62-65`);
the query API returns exactly one list per face (`face_vertices`, `mesh.py:156-157`). What a closed loop
inside a face becomes under that rule (0 bridges = overlap, 1 bridge = invalid, 2 bridges = valid, ring split)
is recorded in [`KNIFE_FACE_CUT_DISCOVERY.md`](KNIFE_FACE_CUT_DISCOVERY.md) §2 FC6 and not repeated.

| Brief claim | Verified | Where |
|---|---|---|
| A face is one ordered boundary list, no hole representation. | ✅ | `mesh.py:8-10, 62-65, 214-238`; V1_SPEC §7 "Face-Boundaries sind geordnet"; `V1_CORE_REVIEW_CLAUDE_003.md` AD-002 (`face_vertices(face_id) -> list[VertexId]`). |
| Holes were never explicitly decided or rejected. | ✅ No document decides or rejects faces with holes. `git log --grep` finds no commit about it. | grep over `docs/`, `src/`, `tests/`, `playground/`, `experiments/` |
| Only "genus tracking" was listed as not built. | ✅, plus three places the brief did not list (below). | `docs/archive/core_v1/CORE_V1_REVIEW.md:134` ("Do not introduce … genus tracking"); `V1_CORE_REVIEW_CLAUDE_002.md:25` ("Explizit NICHT bauen: formale Euler-Operator-Algebra mit Genus-Tracking") |

Additional finds (my grep):

| # | Where | What it says | Relevance |
|---|---|---|---|
| M1-1 | `src/core/mesh.py:24-27` (Core docstring; copies in `tests/mesh.py:24-27` and `experiments/mirai_bastel_core_V1/mirai_bastel_core/mesh.py`, README line 43) | "Bewusst NICHT enthalten: volle Winged-/Half-Edge-Struktur, Non-Manifold-Multi-Shell-Support, Genus-Tracking." | The exclusion lives in the frozen Core's own contract text, not only in reviews. |
| M1-2 | `V1_CORE_REVIEW_CLAUDE_003.md` AD-002 | "Explicitly not V1: full Winged-/Half-Edge topology, twin-pointer/radial structures, …, non-manifold multi-shell support." | Holes are not named; the decision is "ordered boundaries + query API". |
| M1-3 | `KNIFE_FACE_CUT_DISCOVERY.md` §2, §3 ("holes (not representable)"); `playground/experiments/knife_face/decision.md` ("a ring-with-hole, which Mirai's Core cannot represent") | Statements of the current fact, not decisions. | Consistent with this document. |
| M1-4 | `src/viewport/derived.py:72-74` | Fan triangulation "für allgemeine konkave n-Gons eine bewusste Vereinfachung (siehe VIEWPORT_V02_ARCHITECTURE.md Non-Goals: kein allgemeiner Polygon-Trianguliator)". | The cited non-goal is **not** in the non-goals list of `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` §1 (checked). The simplification is real; its cited source is not. Matters for Q2/Q4. |

**Interpretation.** In the Euler-operator literature that the Claude 002 review refers to, "genus tracking"
is the bookkeeping that includes a *ring* term — faces with inner loops (e.g. V − E + F − R = 2(S − H) in
half-edge solid modellers) `[ASSUMED]` (textbook knowledge, not re-read here). Holes were therefore excluded
**implicitly**, together with the Euler-operator algebra, not by a decision about holes. The probe confirms
the arithmetic side: the same visible shape counts χ = V − E + F = 1 when bridged and 2 when the ring is
one face (§4: `outer` has the same V/E/F counts as a holed ring plus its inner face).

---

## 1. Q1 — Reference behaviour

### 1.1 Per tool

**Silo** — closed source.

- `[ART]` The observation in §0.
- `[DOC]` *3D Modeling in Silo: The Official Guide* (Ward, Randall, Nevercenter; Focal Press 2010), search excerpt
  only: Silo "will allow you to create polygons with holes (sometimes filled with another polygon) embedded in
  them"; and, on subdivision, "it is not good to have holes in the mesh … better to have solid polygons
  surrounding an opening". Page/chapter: `[UNKNOWN]`.
- Internal representation, OBJ export of such a face, behaviour of Knife/Connect across the ring: `[UNKNOWN]`.

**Maya** — closed source; API header `MFnMesh.h` (Maya 2016 SP1, mirror `alicevision/mayaAPI`). `[SRC]`

- Faces with holes are **first-class mesh data**: `addPolygon(vertexArray, loopCounts, …)`,
  `addHoles(faceIndex, vertexArray, loopCounts, …)`, `getHoles(holeInfoArray, holeVertexArray)`, and a
  hole-aware `polyTriangulate(points, holes, outerPointsCount, …)`.
- `[DOC]` (API reference, excerpt): `getHoles` returns per hole `[face, numVertices, startIndex]`; in
  `loopCounts` the first entry is the exterior; "Holes should normally be specified with the opposite winding
  order to the exterior polygon."
- `[DOC]` *Make Hole Tool*: "create a hole in a selected polygon face in the shape of a different face"; options
  First/Middle/Second/Project …/None; "Making a hole in a face does not increase the number of faces in your
  polygonal model or change the component indexing for its vertices, edges, or faces."
- `[DOC]` *Mesh > Cleanup*: "Faces with holes" is a *Fix by Tessellation* option next to concave faces — faces
  "valid within Maya, but not in a game console". A third-party tutorial excerpt adds that such faces give
  "terrible results when smoothed" (not official).
- The brief's hint ("holed faces as a cleanup concept") is confirmed, and Maya goes further: holes are part of
  the data model and have a dedicated creation tool.

**Blender** — `source/blender/bmesh/bmesh_class.hh`, main @ `3c582b4`. `[SRC]`

- `// #define USE_BMESH_HOLES` is commented out: "disable holes for now, these are ifdef'd because they use more
  memory and can't be saved in DNA currently". With the define, `BMFace` has `int totbounds` ("one plus the
  number of holes in the face") and a list of loop cycles; `BMLoopList`: "NOTE(@ideasman42): this structure was
  planned for supporting holes in faces. although there are no near term plans for this." The active build has
  one loop cycle per face (`BMLoop *l_first`).
- Footprint of the disabled path (counted in the fetched files): `bmesh_core.cc` 23 `#ifdef`s,
  `bmesh_query.cc` 8, `bmesh_mods.cc` 2, `bmesh_mesh.cc` 2 — and **0** in `bmesh_polygon.cc`
  (normals/tessellation), `bmesh_interp.cc` (attribute interpolation), `bmesh_construct.cc`,
  `bmesh_mesh_validate.cc`. *Interpretation:* the hole path reaches the core element/Euler code but was never
  carried into tessellation, interpolation or validation.
- Closed loop in a face via Knife: island connect (see Knife discovery §1). From `bmesh_polygon_edgenet.cc`: per
  island one connection from its minimum vertex along the sort axis (X in face-projected 2D, only if the island
  has no previous edge) and one from its maximum vertex → typically **two ordinary bridge edges** per island.
- N-gon display: `BM_face_calc_tessellation` uses `BLI_polyfill_calc` (ear clipping; concave-safe)
  (`bmesh_polygon.cc:125, 172`).

**Wings 3D** — master @ `8ae2bfd`. `[SRC]`

- Winged-edge faces are single loops. `#we.holes` ("List of hole faces", `src/wings.hrl:190`) are **hidden
  faces** marking openings in the mesh (`wings_we:create_holes` — "Mark the given faces as holes and hide
  them"; Face|Hole command in `wings_face_cmd.erl:1480-1500` dissolves the selection into one face and hides it).
  A "hole" in Wings is an opening, not an inner boundary of a face.
- `e3d/e3d_mesh.erl:405-410`: "the polygon has a hole; but since the e3d_face record doesn't allow for holes, I'm
  leaving the mesh as is". `make_polygons` (merging triangles across 3DS-style invisible edges, `vis` field
  "Visible edges (as in 3DS)"): "Special care must be taken to eliminate isolated vertices and not to create
  holes. XXX There are knowns problems in this function."
- Holed polygons exist only **transiently at import**: the vector-outline importer builds
  `polyarea{boundary, islands}` (`plugins_src/import_export/wpc_ai.erl`) and converts it with
  `e3d__tri_quad:quadrangulate_face_with_holes` — `joinislands` splices each hole into the outer loop through
  one diagonal (a keyhole), then triangulates, runs a constrained Delaunay pass against the true border edges and
  merges triangles into quads. Result: ordinary single-loop faces.
- Face-interior cutting: Connect excludes faces (Knife discovery §1).

**3ds Max** — closed source; SDK header `mnmesh.h` (Max 9 SDK, mirror `phoenixzz/SGPEngine`). `[SRC]`

- `class MNFace { int deg; int *vtx; int *edg; int *diag; … }` — one vertex/edge cycle plus triangulation
  diagonals. "Holes" in the header refer only to mesh openings (find/fix holes, border loops).
- `[DOC]` Editable Mesh: edges carry visibility — "Invisible edges (also called construction lines)"; Editable
  Poly polygons are triangles whose completing edges are hidden (Turn edge). A visibility flag on real edges is
  an established pattern (relevant to H2).
- `[DOC]` ShapeMerge "Cookie Cutter": "the shape is a hole in the mesh object" — representation of the result
  `[UNKNOWN]`.

**Modo** — `[DOC]` Curve Fill: "If curves have opposite directions, it can cut holes." What the filled result is
(holed polygons or re-meshed faces) and whether Modo polygons can carry holes at all: `[UNKNOWN]`.

**Exchange formats**

- **OBJ** `[DOC]`: the `hole` statement exists only for free-form surfaces ("builds a single inner trimming
  loop"); a polygon `f` line is one vertex list. Mirai's loader reads `f` as one index tuple `[CODE]`
  (`examples/loaders/obj_loader.py:133-140`); Mirai has no OBJ exporter `[CODE]`.
- **USD** `[SRC]` (`pxr/usd/usdGeom/schema.usda`, release @ `ee47c67`): faces are single loops; `holeIndices` =
  "The indices of all faces that should be treated as holes, i.e. made invisible. This is traditionally a feature
  of subdivision surfaces and not generally applied to polygonal meshes." — the Wings pattern, not inner loops.

### 1.2 Summary

| Tool / format | Loops per face (data) | What "hole" means | Closed shape inside a face becomes | Evidence |
|---|---|---|---|---|
| Silo | outer + holes (per guide) | inner boundary, "sometimes filled with another polygon" | ring = 1 face with hole + inner face | `[ART]`, `[DOC]` |
| Maya | 1 exterior + n holes | inner boundary of a face | Make Hole: face keeps its index and gains a hole | `[SRC]`, `[DOC]` |
| Blender | 1 (holes compiled out) | — (planned, disabled) | Knife: island + 2 ordinary bridge edges → n-gons | `[SRC]` |
| Wings 3D | 1 | hidden face = opening | Connect: no face points; import: keyhole → triangulate → quads | `[SRC]` |
| 3ds Max | 1 (+ diagonals) | opening; separately: invisible edges | Cut: see Knife discovery; ShapeMerge result `[UNKNOWN]` | `[SRC]`, `[DOC]` |
| Modo | `[UNKNOWN]` | Curve Fill "can cut holes" | `[UNKNOWN]` | `[DOC]` |
| OBJ | 1 per `f` | trimming loop of free-form surfaces only | must be converted on export | `[DOC]` |
| USD | 1 | invisible face | — | `[SRC]` |

**Observation.** Of the examined tools, holed faces are data only in Maya (verified in its API) and Silo (guide
excerpt + Artist). Blender designed them and compiled them out. Wings, 3ds Max and USD keep faces single-loop
and use "hole" for an opening or an invisible face. Every single-loop tool that meets a holed polygon (Knife
islands, vector import) resolves it into ordinary faces with bridges or a keyhole plus triangulation. Silo's guide
and Maya's Cleanup both treat holes as something to resolve before subdivision or export.

**Interpretation.** Holed faces are a minority representation among polygon modellers — but the Artist's
reference tool has them. Where they exist they come with a triangulation that understands holes (Maya
`polyTriangulate(…, holes, …)`) and a cleanup path back to ordinary faces.

---

## 2. Q2 — Impact inventory ("one boundary per face")

Consequences are stated for H1 (inner loops in Core). The "silent" rows matter most: if the Core kept
`face_vertices()` = outer loop only (backward compatible), nothing would crash — consumers would quietly produce
wrong geometry (probe `outer`, §4).

| Subsystem | Assumption today | Consequence with inner loops | Evidence `[CODE]` |
|---|---|---|---|
| Face storage + query API (AD-002) | one ordered `boundary` list; `face_vertices` → `list[VertexId]` | new storage + new query (e.g. loops per face); decide whether `face_vertices` means outer loop (silent errors below) or breaks callers | `mesh.py:62-65, 156-169`; V1_SPEC §7 |
| `add_face` | one cycle; no repeated-vertex check (Knife discovery H7) | hole-aware constructor or `add_hole`; loop-disjointness check | `mesh.py:214-238` |
| Edge lookup / incidence | one edge per unordered vertex pair; `edge_faces` 0–2 | unchanged in principle (inner-loop edge: holed face + inner face or none); `face_edges` must include inner-loop edges or get a sibling query | `mesh.py:110-112, 159-172, 204-212` |
| Invariant catalogue | per face: ≥ 3, no duplicates, `len(face_edges) == len(boundary)`, bidirectional incidence, ≤ 2 faces/edge | per loop; cross-loop disjointness; inner-loop winding. **No winding check exists today at all** (§4, §6) | `tests/mesh_invariants.py:46-82` |
| `split_edge` | inserts the new vertex into every face boundary containing the pair | must search inner loops too, else incidence breaks | `mesh.py:318-329` |
| `collapse_edge` | dedupes one boundary; drops face if < 3 | inner loop < 3 → hole vanishes (genus change); loops touching after collapse → new invalid state | `mesh.py:398-425` |
| `connect_vertices` | index slicing of one boundary | outer↔inner connection is the "kill ring" case: the face stays one face and loses its hole — undefined today; one connect cannot split a holed face | `mesh.py:440-475` |
| `remove_face` | removes face, keeps its edges | unchanged; note for H0: bridges become free edges after deleting the ring (§4) | `mesh.py:261-278` |
| Euler / genus | not tracked (excluded, §0) | V − E + F stops being the invariant (1 bridged vs 2 holed for the same shape, §4); a ring term would be needed | `mesh.py:24-27` |
| History (`MeshStateCommand`) | full `export_state()` snapshots | mechanism unchanged if `export_state` carries loops | `operations/topology.py:35-53` |
| Serialization | `faces: {fid: [vids]}`, `FORMAT_VERSION = 1` | format change: additive key (AD-SYM-01 precedent, no version bump — but a reader ignoring the key silently fills every hole) or version bump | `mesh.py:496-516`; `serialization.py:22-33` |
| OBJ import / export | `f` → one list; no exporter | import unaffected (OBJ has no polygon holes); a future exporter must bridge or triangulate | `obj_loader.py:133-140`; `scene_factory.py:66-81` |
| Display triangulation | fan from `boundary[0]` | outer-only fan fills the hole; needs hole-aware triangulation at every fan — 4 `triangulate_face` call sites + 2 inline fans in `picking.py` (`src`), 3 call sites in `playground`. H0 already needs a concave-safe one (§4 `fc6`) | `derived.py:69-82`; `render_mesh.py:144-154`; `overlay.py:232-236`; `playground/vbo_builder.py:37, 120`; `playground/window.py:786` |
| Face normals | normal of the first fan triangle | outer loop fine; for concave faces the first fan triangle is not guaranteed to agree with the face (did agree in §4) | `derived.py:138-147, 175-184`; Newell only in `extrude.py:42-57` |
| `pick_face` / occlusion / pick cache | ray vs fan triangles; bbox from `face_vertices` | a click inside the hole hits the ring; occlusion treats the hole as opaque | `picking.py:194-224, 231-262`; `picking_cache.py:68-80` |
| Edge picking / wireframe | every edge drawn and pickable | unaffected by H1; H2 needs a skip rule here | `wireframe.py:16-23`; `picking.py:108-144` |
| Selection / highlight / Move vertices | face → `face_vertices` | inner-loop vertices missing → moving a holed face leaves its hole behind | `selection_helpers.py:49-54`; `overlay.py:127-131, 155-158`; `application.py:135` |
| Transform normal / tangent basis | `face_verts[0..1]`, averaged face normals | outer loop fine | `transform.py:142-158`; `selection_helpers.py:85-131` |
| Edge / Vertex Connect (per face) | boundary-order walk, adjacency by index distance | pairing rules undefined for vertices on inner loops | `connect_vertices_per_face.py:25-37`; `connect_per_face.py:58-80` |
| Knife (Production) | shared-face test by boundary index distance → `connect_vertices` | target on the inner loop of the current face = kill-ring, not a split | `knife.py:35-48`; `topology_points.py:38-62` |
| Extrude (Playground AP-05) | walls on edges with exactly one selected face; cap = `face_vertices` | outer-only: no walls on the inner loop, cap fills the hole — Silo's "recess with a hole" not reproduced | `playground/topology_tools/extrude.py:177-197` |
| Edge ring (Playground) | steps through faces with exactly 4 `face_edges` | a holed quad counts as a quad → the ring passes through it (semantic question) | `playground/topology_tools/loop_ring.py:85-92` |
| Subdivision (future) | none implemented; Catmull-Clark planned | not defined for holed faces; would need bridging inside the derived pipeline. Silo's guide and Maya's Cleanup both flag holes for smoothing (Q1) | V1_SPEC §11 |
| Symmetry (AD-SYM-01/02) | correspondence is per vertex position; Seam = EdgeIds | H1 unaffected. H0: bridge placement by "nearest vertex" may pick non-mirrored corners on the two sides; vertex-only correspondence would not detect that asymmetry `[ASSUMED]` | `symmetry.py:118, 194` |
| Morph / Skin provenance (ARCH-02) | each primitive documents surviving / new IDs; parent context via operation (AD-017 B5) | H1: adding a hole can keep the FaceId (Maya: "does not … change the component indexing") → face-level data survives. H0: parent face dies, 3 new faces. H2: the bridge flag *is* provenance | `mesh.py:18-22`; AD-017 B5; ROADMAP ARCH-02 |

Scale `[CODE]`: `face_vertices` / `face_edges` / `edge_faces` / `triangulate_face` are called in 14 files in
`src/` (incl. `mesh.py`), 17 in `playground/` (incl. its tests), 19 in `tests/`.

---

## 3. Q3 — Options

### H0 — Status quo: bridges (storage = display = selection)

A closed shape is stored as the inner face plus a ring split by 2 bridge edges (Knife discovery FC6).

- **Freeze rule (§7).** (1) Requirement: a closed shape inside a face — observed in Silo `[ART]`, built as Lab
  task 5; whether it is *required* is A1/A3. (2) Solvable with the public API:
  yes — two `split_face_path` calls or the Lab stand-in (B2b surgery); the clean route is the existing B2c
  question from the Knife discovery §3, nothing new. → no Core change for the representation.
- **Core surface:** none new.
- **Artist-visible differences vs Silo** (`[PROBE]` §4 unless noted):
  - wireframe shows 2 extra edges;
  - the ring is 2 faces — a click selects half of it; ring actions need both selected;
  - delete triangle → hole, same as Silo;
  - delete ring (both faces) → the 2 bridges stay as **free edges** hanging across the hole (`remove_face` keeps
    edges, `mesh.py:261-272`) unless the delete tool removes them;
  - extrude ring (both faces, Playground Extrude) → 7 walls (outer 4 + inner 3), bridges internal — the same
    recess as Silo's, with the 2 bridge edges visible on the cap;
  - bridge placement is a tool policy (Lab: world-space nearest vertex) and creates concave ring faces.
- **Hidden costs, needed anyway:** concave-safe triangulation for render and `pick_face` (§4 `fc6`: 11.9 %
  double coverage; a click in the triangle's centre picks a ring face) — the same need Face Cut's notch shape
  already creates (Knife discovery H2); a correct bridge construction (§6); free-edge cleanup on delete.
- **Enables:** Knife closed shape now (Lab D exists); region extrude over the ring (§4); region inset would follow
  the same boundary-edge rule `[ASSUMED]`.
- **Blocks:** nothing permanently — but once bridges are stored as ordinary edges, a later move to H1/H2 cannot
  tell them from user edges (§4: 17 interior edges, topology gives no distinction). Keeping that door open costs
  a recorded origin, which is H2's flag (below).
- **Risk:** low for the Core; medium for UX (visible difference from the reference tool).

### H1 — Holes in Core (face = outer loop + inner loops)

- **Hard invariants (sketch):** every loop ≥ 3 distinct vertices; no vertex shared between loops of the same
  face (no touching loops); inner loops with opposite winding to the outer loop (Maya's convention, `[DOC]`);
  each loop edge lists the face in `edge_faces`; ≤ 2 faces per edge unchanged. Geometric containment (inner loop
  inside outer, loops not crossing) not checked by Core, consistent with today's "no geometric checks".
- **ID rules:** adding a hole keeps the FaceId (Maya precedent) — the one clear ARCH-02 advantage. Open: does a
  hole get its own identity (a new ID type next to AD-001's three) so selection and history can name it?
- **Operations affected:** every row of Q2 marked for H1 — `add_face`, `split_edge`, `collapse_edge`,
  `connect_vertices` (kill-ring semantics), `remove_face`, invariants, `export_state`/`load_state`, display
  triangulation (hole-aware, e.g. keyhole + ear clipping, or CDT as in Wings), picking, selection→vertices,
  Connect, Knife, Extrude, ring traversal, future subdivision (needs bridging anyway).
- **Migration of existing tests:** additive if `face_vertices` keeps meaning "outer loop" and no existing
  construction creates holes — today's tests stay green. The risk is the reverse: green tests while every
  consumer silently mishandles holes. New test matrix: each primitive × {face without hole, face with hole, edge
  on an inner loop}.
- **Freeze rule (§7).** (1) Requirement: only "Silo does it" so far — not yet a concrete Artist requirement
  that the ring must be one face (A1, A3). (2) Not solvable with the public API (one list per face). (3)/(4) The
  smallest extension is not small: it amends AD-002's central contract ("ordered boundaries"), not an additive
  primitive like `add_edge` or `split_edge(t)`. → an architecture decision (Type C gate), not a §7.1 exception.
- **Enables:** Silo-identical ring (one face, no extra edges), hole survives deleting the inner face, FaceId
  continuity. Knife closed shape = one `add_hole`-style primitive.
- **Blocks / complicates:** subdivision (holes must be bridged in the derived surface), OBJ export, every
  per-face tool rule.
- **Risk:** highest. Blender is the reference case: planned, partially built, compiled out, "no near term plans";
  the path never reached tessellation, interpolation or validation (§1.1).

### H2 — Bridged storage, holed presentation

Storage as H0; bridges carry a persistent "hidden / construction" flag; render and selection group the ring
faces across hidden edges and present them as one face.

- **Where the flag must live.** It must survive Undo and save/load. AD-SYM-01 §1.1 measured that an
  ID-bound declaration kept outside `Mesh` desynchronizes on Undo; the same holds here. It cannot be derived
  either: topology and face normals do not distinguish a bridge from any other interior edge (§4). → additive Core
  state, like `symmetry_definition`.
- **Every mutation must maintain it** — unlike `symmetry_definition`, which is only stored. One `split_edge` on
  a bridge turns one hidden edge into two visible ones (§4); `collapse_edge`, `connect_vertices`, extrude caps
  (new edge IDs), delete (hidden free edges left behind) all need rules. Either the primitives' ID-continuity
  contracts grow a flag clause (Core), or tools do the bookkeeping (the B2b pattern the Knife discovery criticised).
- **Presentation layer:** wireframe and edge picking skip flagged edges; face picking maps a FaceId to its group;
  hover/selection highlight the group; triangulation is still per real face (so H0's concave-safe triangulation is
  still needed). A Knife cut drawn across the ring may cross a hidden bridge → it is a cross-face segment (Knife
  discovery Q5) although the Artist sees one face.
- **Subdivision:** the bridges are real edges; the smoothed surface shows their influence. The illusion ends at
  the derived surface.
- **Hack or clean layer? (agent assessment).** Clean only if (a) the flag is Mesh-owned state, (b) every
  primitive's contract says what happens to it, (c) the grouping is derived, not stored. Without (a)–(b) it is
  a hack: the probe's split case already breaks it. With (a)–(b) it is the first concrete provenance record
  ("this edge is not user-authored") — so it belongs to ARCH-02, not to the Knife. Precedents: 3ds Max invisible
  edges `[DOC]`, Wings' 3DS `vis` bits `[SRC]` — whose importer notes the hole problem at exactly the
  flag→polygon boundary.
- **Freeze rule (§7):** additive Core state + contract clauses on existing primitives → AD required.
- **Risk:** medium-high; looks cheaper than it is.

### Further options found

| Option | Source | What it is | Assessment |
|---|---|---|---|
| **H3 — hole = hidden face** | Wings `#we.holes` `[SRC]`; USD `holeIndices` `[SRC]` | An opening is kept as an invisible face so the mesh stays closed. | Answers "openings", not "inner boundary of a face" — does not make the ring one face. Relevant only as a precedent that presentation flags on topology are an established pattern. |
| **H4 — transient holes** | Wings vector import (`polyarea` → `quadrangulate_face_with_holes`) `[SRC]`; Maya `polyTriangulate(points, holes, …)` `[SRC]` | A holed polygon exists only as *input* to a construction step (Knife closed shape, later Fill/Cap); the stored result is ordinary faces. | = H0 with the bridge policy replaced by a meshing policy. No Core change. |
| **H5 — ring meshing instead of 2 bridges** | Silo guide: "solid polygons surrounding an opening" `[DOC]`; Wings quadrangulate `[SRC]`; inset-style rings `[ASSUMED]` | Connect the inner loop to the outer loop with more than 2 edges (e.g. one per inner vertex or outer corner) so ring faces are convex quads/triangles. | No concave faces → fan triangulation stays valid; subdivision-friendlier; more edges the Artist did not click (Knife discovery A7). Tool policy only. |

### Comparison

| | H0 bridges | H1 holes in Core | H2 hidden bridges | H4/H5 (tool policy) |
|---|---|---|---|---|
| Core surface | none | AD-002 contract + all primitives + format | additive flag + clauses on all primitives | none |
| §7 | passes (no change) | Type C gate; requirement not yet concrete | AD needed | passes |
| Ring = one face for the Artist | no | yes | yes (presented) | no |
| Extra visible edges | 2 | 0 | 0 (3ds Max shows its invisible edges at Edge level `[DOC]`; Knife crossings expose them) | ≥ 2 |
| Knife closed shape | now (Lab) | new primitive | Lab + flag | Lab + policy |
| Extrude / inset of the ring | region of 2 faces works (§4) | every tool must handle inner loops | as H0 + flag propagation | region works |
| Subdivision (none built yet) | works; bridges shape the result `[ASSUMED]` | needs bridging in derived pipeline | bridges visible in smooth result `[ASSUMED]` | convex ring faces, likely best (H5) `[ASSUMED]` |
| ARCH-02 | parent face dies; bridges indistinguishable later | FaceId can survive | flag = provenance | as H0 |
| Main risk | UX difference vs Silo | cost, silent consumer errors | flag drift | extra edges |

**Agent assessment (not a decision).** H0 is the zero-Core baseline and is already buildable; its real costs are
outside the Core and partly needed for Face Cut anyway (concave-safe triangulation, a correct bridge
construction). H1 is the only option matching Silo one-to-one, but it reopens AD-002's central contract and
touches every face consumer; the evidence (Blender compiled it out; Silo's own guide and Maya's Cleanup steer
away from holes before smoothing) suggests high cost for a state that may be intermediate — A3 decides whether
that is so. H2 is a provenance question in disguise and should be judged under ARCH-02, not as a render trick.
A sensible order *if* the Artist agrees: keep H0 for the Lab, fix the stand-in (§6), ask A1–A3; open an H1 gate
only if A1 = REJECT or A3 says holes stay in finished models; consider H2 only if A1 = ITERATE because of the
*visible* bridges. H5 is a cheap variant of H0 worth showing next to it if the bridges' shape is the complaint.

---

## 4. Q4 — Probe

`python experiments/topology/face_holes_probe.py` — 3×3 grid of unit quads (z = 0, faces CCW seen from +Z), a
triangle (1.3, 1.3)–(1.7, 1.3)–(1.5, 1.7) inside the centre quad. Constructions:

- `lab-ccw` / `lab-cw` — the Lab D stand-in (`select_bridge` + `close_loop_with_bridges`, imported unchanged
  from `playground/experiments/knife_face/engine.py`), loop clicked counter-clockwise (the order the Lab's own
  test uses) / clockwise;
- `fc6` — Knife discovery FC6 "2 bridges": two `split_face_path` calls from the quad's corners;
- `outer` — outer quad unchanged + inner triangle face = what any current consumer would see of a holed face
  if `face_vertices()` kept meaning "outer loop" (structurally FC6 "0 bridges").

Coverage = 40×40 samples over the centre quad, faces covering each point (0 = gap / 1 / ≥ 2 = overlap),
once as true polygons and once as the fan triangles that `RenderMesh` and `pick_face` use.

| | `lab-ccw` | `lab-cw` | `fc6` | `outer` |
|---|---|---|---|---|
| Invariant catalogue | OK | OK | OK | OK |
| Face sizes (ring) | 5 + 6 | 4 + 7 | 5 + 6 | 4 (one face) |
| V − E + F (grid: 1) | 1 | 1 | 1 | **2** |
| Interior edges with inconsistent winding | **3** | **3** | 0 | 0 |
| Inner face normal | +Z | **−Z (flipped)** | +Z | +Z |
| Ring + inner area (quad = 1.0) | **1.16** | 1.00 | 1.00 | 1.08 |
| Coverage as polygons (gap / 1 / ≥ 2) | 0 / 92.0 / **8.0 %** | 0 / 100 / 0 % | 0 / 100 / 0 % | 0 / 92.0 / 8.0 % |
| Coverage as fan triangles | 0 / 67.5 / **32.5 %** | 0 / 67.2 / **32.8 %** | 0 / 88.1 / **11.9 %** | 0 / 92.0 / 8.0 % |
| Fan triangles flipped (ring faces) | 1, 2 | 0, 2 | 1, 1 | 0 |
| `pick_face` at triangle centroid | inner | inner | **ring face** | inner |

IDs (all three bridged constructions): the centre face becomes invalid; new VertexIds / FaceIds above the previous
maxima (AD-001); the centre quad's 4 boundary edges keep their IDs. Bridges are ordinary 2-face edges.

Silo comparison (`lab-ccw`, `fc6`):

| Action | Result |
|---|---|
| delete inner face | hole bounded by the 3 loop edges (now 1-face edges); 0 free edges; invariants OK |
| delete ring (both faces) | invariants OK; **the 2 bridges remain as free edges** across the hole |
| extrude ring (Playground `ExtrudeTool`, both faces) | 7 walls (outer 4 + inner 3), bridges internal, 2 caps; `lab-ccw` carries its 3 winding mismatches into the result |

H2 flag fragility (`fc6`): after `split_edge` on a bridge, 1 of 2 flagged EdgeIds is invalid and neither new half is
flagged; `load_state(before)` (Undo) makes both valid again. 17 interior edges, the 2 bridges among them are
indistinguishable by topology, and both ring faces have identical face normals.

**Observation.** (1) Bridged storage is valid under today's invariants and ID rules. (2) Today's fan triangulation
is wrong for the concave ring faces of all three bridged constructions — double-covered area, and in `fc6` a click in
the middle of the triangle selects a ring face. (3) The invariant catalogue passes constructions that overlap
(`lab-ccw`) or flip a face (`lab-cw`); it checks neither winding nor geometry. (4) A holed face read through a
single-loop API (`outer`) renders and picks like a filled quad with a triangle on top.

**Interpretation.** A hole-aware triangulation (H1) and a concave-safe triangulation (H0/H2) are the same piece of
work plus the hole splice; H0 needs the second regardless of this question. A winding check belongs in the
invariant catalogue (test code, not Core) whatever option is chosen.

---

## 5. Q5 — Artist questions (M4)

At most three; each has a test situation that takes minutes. Answers: **KEEP / ITERATE / REJECT / UNKNOWN**.
Play them after the Lab stand-in is fixed (§6) — or judge edges and selection only, not shading.

**A1 — Two bridges vs one ring face.** *Test:* `python playground/run.py grid`, `Tab` to `knife_face`, variant D,
`C`, three clicks inside one quad, `Enter` (Lab task 5). Look at the wireframe (2 extra edges), switch to face mode and click
the ring (only half highlights). Do the same cut in Silo.
*Question:* Is the Mirai result usable for your work?
KEEP = bridges and a 2-face ring are fine (→ H0) · ITERATE = fine if the bridges are hidden and the ring selects
as one — say which of the two matters (→ H2 or H1) · REJECT = it must be one face with a hole, like Silo (→ H1) ·
UNKNOWN.
*Optional, 1 minute:* export that Silo scene as OBJ and share the file — OBJ cannot hold a holed polygon, so the
file shows how Silo resolves it.

**A2 — Extrude the ring.** *Test:* in Silo, extrude the ring from A1. In the Playground, select **both** ring faces
(Shift-click adds the second) and extrude (`E` in face mode).
*Question:* Same result for your purpose?
KEEP = yes · ITERATE = shape right, the 2 edges on the cap bother me · REJECT = I need to extrude the ring as one
face with one click · UNKNOWN.
*Also note* what you normally do next with such a ring: extrude it, cut across it with the Knife, or delete it.

**A3 — Final state or intermediate?** *Test:* in Silo, after the A1 cut, turn on subdivision / smooth preview and
look at the ring.
*Question:* Do holed faces stay in your finished (smoothed) models?
KEEP = yes, they stay (→ H1 must also solve subdivision) · ITERATE = only temporarily; I connect them to the outer
edges before smoothing (→ H0/H5 suffice; the question becomes *where* the bridges go) · REJECT = I don't use this
when modelling, it was an observation (→ close the topic at H0) · UNKNOWN.

---

## 6. Observations outside the question

- **Lab closed-shape stand-in has a winding defect** `[CODE]` `[PROBE]`. `close_loop_with_bridges` builds the
  inner face in click order and walks both loop arcs forward (`playground/experiments/knife_face/engine.py:345-350`),
  so the inner face and the ring faces always traverse the loop edges in the same direction. Counter-clockwise
  clicks (the order in `test_d_three_interior_points_then_commit_is_closed_shape`): the ring faces overlap the
  triangle (area 1.16 of 1.0). Clockwise clicks: a clean partition, but the inner face's normal is flipped. Both
  pass the invariant catalogue and the Lab's tests. This affects what the Artist sees in Lab task 5 / A1. Not fixed
  here (the Lab is out of scope); the Knife Lab handoff owns it. `fc6`'s construction (two `split_face_path`
  calls) does not have the defect.
- **Delete leaves bridges** `[PROBE]`: deleting both ring faces leaves the 2 bridges as free edges
  (`remove_face` keeps edges by design, `mesh.py:261-272`). Whoever builds "delete face" for bridged rings needs a
  rule for them.
- **Concave faces and fan triangulation** `[PROBE]`: independent of holes, a concave face is mis-triangulated for
  render and pick unless its first boundary vertex happens to see the whole face (measured for the bridged rings; the
  Knife notch FC3 is the same class `[ASSUMED]`); M1-4 notes that the cited non-goal for this does not exist
  in the viewport document.

---

## 7. Confidence per question

| Q | Confidence | Basis |
|---|---|---|
| Q1 | **partly** | Blender, Wings, USD from source; Maya and 3ds Max from public API/SDK headers (third-party mirrors) plus doc excerpts; Silo from one guide excerpt + the Artist; Modo only one excerpt. No tool was run. |
| Q2 | **documented** | Code read at `3a7576e` with file:line; H1 consequences are derived, not implemented. |
| Q3 | **documented** (costs, freeze-rule check) / **interpretation** (assessment) | Q2 + probe; the assessment is marked as such. |
| Q4 | **documented** | Probe output, reproducible. |
| Q5 | **prepared** | Not asked yet. |

## 8. Not investigated

- Silo's internal representation, its OBJ export of a holed face, Knife/Connect across a holed ring, and Silo's
  subdivision of it (A1–A3 ask for this); Modo's polygon model; none of the reference tools was run.
- Maya/3ds Max documentation pages in full (blocked); 3ds Max Cut / ShapeMerge results.
- Holes touching the outer loop (shared vertex), nested islands (a shape inside the inner face), several holes in one
  face, holes in non-planar faces.
- Attributes (UV, weights, morphs) across H0/H1/H2 beyond the FaceId-continuity point.
- The Symmetry Lab's mirrored Knife engine (WP-SYM-LAB-01 Slice 6) with closed shapes.
- Cost of a concave-safe or hole-aware triangulator in Python per frame (performance).
- Lab task 5 has not been played.

## Sources

- Blender `bmesh_class.hh`, `bmesh_core.cc`, `bmesh_query.cc`, `bmesh_mods.cc`, `bmesh_mesh.cc`, `bmesh_polygon.cc`,
  `bmesh_polygon_edgenet.cc`, main @ `3c582b4` —
  https://github.com/blender/blender/tree/main/source/blender/bmesh
- Wings 3D master @ `8ae2bfd` — https://github.com/dgud/wings (`src/wings.hrl`, `src/wings_we.erl`,
  `src/wings_face_cmd.erl`, `e3d/e3d_mesh.erl`, `e3d/e3d__tri_quad.erl`, `plugins_src/import_export/wpc_ai.erl`)
- OpenUSD `pxr/usd/usdGeom/schema.usda`, release @ `ee47c67` — https://github.com/PixarAnimationStudios/OpenUSD
- Maya API `MFnMesh.h` (2016 SP1, third-party mirror) —
  https://github.com/alicevision/mayaAPI/blob/master/2016.sp1/linux/include/maya/MFnMesh.h
- Maya Help, Make a hole in a polygon face (excerpt) —
  https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-A12186FB-8B18-4492-8CB9-BAB6BC54223F
- Maya Help, Cleanup Options (excerpt) —
  https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=GUID-AB60C982-C96E-4947-8CF3-5152406B6A40
- Maya API, MFnMesh class reference (excerpt) —
  https://help.autodesk.com/cloudhelp/2024/ENU/MAYA-API-REF/cpp_ref/class_m_fn_mesh.html
- 3ds Max 9 SDK `mnmesh.h` (third-party mirror) —
  https://github.com/phoenixzz/SGPEngine/blob/master/Tools/SGP_MAX9Plugins/MAX9SDK/include/mnmesh.h
- 3ds Max Help, Editable Mesh (Edge) (excerpt) —
  https://help.autodesk.com/cloudhelp/2020/ENU/3DSMax-Modeling/files/GUID-FB9EB9D3-7758-4C44-959D-8BCE622AC4E2.htm
- 3ds Max Help, ShapeMerge Compound Object (excerpt) —
  https://help.autodesk.com/view/3DSMAX/2024/ENU/?guid=GUID-50D6A2B6-D4D8-4BE7-A416-CE80AFFEEA7F
- *3D Modeling in Silo: The Official Guide* (excerpt) — https://books.google.com/books/about/3D_Modeling_in_Silo.html?id=q4RUP0ISeCIC
- Modo Help, Curve Fill (excerpt) — https://learn.foundry.com/modo/content/help/pages/modeling/duplicate_geometry/curve_fill.html
- Wavefront OBJ specification (excerpt) — https://paulbourke.net/dataformats/obj/obj_spec.pdf
