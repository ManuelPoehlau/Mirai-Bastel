# Mirai / N-World System Extraction

> Living research document. Primary/contemporary evidence first; observations and hypotheses are explicitly marked.

## Evidence legend

- **[PRIMARY]** original documentation, developer statement, archived software, first-party historical material
- **[CONTEMPORARY]** period documentation/review/report
- **[OBSERVED]** visible in demos or direct-use reports, but not proof of internal implementation
- **[SECONDARY]** later recollection/reference; useful as a lead
- **[HYPOTHESIS]** our technical interpretation
- **[DESIGN]** deliberate Mirai-Bastel decision

---

# 1. System / Editor Architecture

**[PRIMARY/CONTEMPORARY]** The S-Graphics/N-World/Mirai lineage is described as an integrated 2D/3D graphics suite. The surviving historical archive explicitly points to the N-World 3.0 online documentation. [1]

**[CONTEMPORARY]** A December 1999 *Game Developer* review describes Mirai as more like a **"3D operating system"** than a conventional UI: modules behave like applications, have their own dialogs, and are dynamically linked so changes propagate between them. It also notes multiple windows of the same type and hot-linking to modules such as paint. [2]

**[CONTEMPORARY]** The same review says Mirai uses minimal icons and no tooltips; interaction relies heavily on left/middle/right mouse clicks, with results dependent on **sequence and context**. [2]

**[HYPOTHESIS]** This suggests a shared asset/state model with multiple specialized editors/views rather than isolated tools.

```text
Shared Asset / Scene State
          │
   ┌──────┼──────┐
   ↓      ↓      ↓
Geometry Animation Paint
 Editor    Editor   Editor
   └──── live links ────┘
```

**[DESIGN]** Mirai-Bastel should eventually separate asset/model state from editor/view implementations.

---

# 2. Selection

**[CONTEMPORARY]** The 1999 review explicitly says selection defines available options to a greater degree than in other programs. Clicking geometry can switch to camera mode; clicking an edge or polygon brings up actions applicable to that element. [2]

**[CONTEMPORARY]** Mirai's modeling tools operated on vertices, edges and faces; alignment and beveling are specifically mentioned. Edge loops were used to organize character topology around contours and muscle formations. [3]

**[HYPOTHESIS]** Selection is part of a context system, not merely a boolean set:

```text
Hover element
     ↓
Element type + selection state
     ↓
Available operations
     ↓
Mouse / modifier interpretation
```

**[DESIGN]** V1 selection modes remain Vertex / Edge / Face. Soft Selection is an influence layer, not a fourth selection mode. Loop/ring navigation must be possible in the topology API even if not all UI operations ship in V1.

---

# 3. Mouse Interaction / Context

**[CONTEMPORARY]** Mirai's clean interface was driven by LMB/MMB/RMB, with results dependent on sequence and context. The geometry view could also become camera mode. [2]

**[OBSERVED/SECONDARY]** Later direct-user reports describe very deep context sensitivity, including modifier/mouse variants of Magnet Move and different falloff coordinate choices. This remains a lead until confirmed against original documentation or software. [4]

**[HYPOTHESIS]** The interaction model is best understood as a state machine:

```text
Idle
 │
 ├─ Hover Vertex → Vertex context
 ├─ Hover Edge   → Edge context
 ├─ Hover Face   → Face context
 └─ Empty View   → Camera context

Context + Mouse + Modifier + Sequence
                  ↓
              Operation
```

**[DESIGN]** Input gestures resolve to operations; they do not directly mutate mesh arrays.

---

# 4. Modeling

**[CONTEMPORARY]** Mirai had an unusually extensive modeling toolset for its era. The review mentions alignment and beveling of vertices/edges/faces, edge-loop organization, extrusion, subdivision and smoothing. [3]

**[CONTEMPORARY]** Mirai was fundamentally polygon/subdivision based and did not rely on NURBS/B-splines/H-splines for organic modeling. [3]

**[CONTEMPORARY]** Its "Volume Modeling" approach used a low-resolution geometric form and a higher-resolution smoothed **Derived Surface**. Changes to the control volume updated the derived surface. [3]

**[HYPOTHESIS]** The important abstraction was therefore not simply a polygon mesh plus a display smooth toggle, but an editable control volume continuously evaluated as a derived surface.

**[DESIGN]** Mirai-Bastel's control mesh remains authoritative; subdivision is derived.

---

# 5. Soft Selection / Magnet

**[CONTEMPORARY]** The August 1999 Mirai update introduced **magnet moves along face normals with falloff**. The review says this could be used to "paint" surface deformations/displacements such as cheekbones, brows, and layers of clothing or armor. [3]

**[CONTEMPORARY]** The April 2000 update again lists Magnet Move as moving multiple vertices along normals with falloff. [5]

**[OBSERVED/SECONDARY]** A later user report describes Magnet Move as deeply context-driven and claims modifier/button combinations expose additional falloff coordinate options. [4]

**[HYPOTHESIS]** Magnet Move combines influence/falloff, surface-normal direction and context-dependent interaction. It is conceptually richer than simply selecting a wider set of vertices.

**[DESIGN]** Mirai-Bastel should implement Influence/Falloff as a reusable subsystem usable by Move, Rotate, Scale, Tweak, Extrude and future deformation tools.

---

# 6. Topology

**[PRIMARY]** Bay Raitt's own professional description identifies Mirai's modeller with a **Winged Edge data structure** and traces it to Symbolics S-Geometry. [6]

**[CONTEMPORARY]** Edge loops and their extrusion are described as important to character modeling. [3]

**[SECONDARY]** N-World is repeatedly documented as the source from which the Mirai/Nendo/Wings lineage emerged, with the N-World winged-edge modeler inspiring Nendo and subsequently Wings3D. [7]

**[DESIGN]** We will compare Winged Edge, Half Edge, radial-edge and hybrid indexed approaches before freezing the mesh core. Historical fidelity is valuable, but the goal is the interaction capability, not copying an obsolete implementation blindly.

---

# 7. Subdivision / Derived Surface

**[CONTEMPORARY]** Mirai's "Volume Modeling" used a control volume and high-resolution smoothed Derived Surface. Changes to the control volume updated the derived surface. [3]

**[CONTEMPORARY]** The review highlights multiple levels of detail from the control volume, stable face count under surface deformation, and the fact that the control volume could behave like a lattice deformer for poses and morph targets. [3]

**[HYPOTHESIS]** Subdivision was therefore part of the modeling/deformation abstraction, not merely a viewport display effect.

```text
Editable Control Mesh
        ↓
Derived / Subdivided Surface
        ↓
Deformation / Pose / Morph
        ↓
Continue editing control mesh
```

---

# 8. Animation / Morph / Deformation

**[CONTEMPORARY]** The 1999 review describes advanced FK/IK, motion capture, motion layering and facial animation. [2]

**[CONTEMPORARY]** It describes the skeleton responding to magnet moves and a pose-oriented workflow rather than only individual joint rotations. [3]

**[CONTEMPORARY]** The control volume could act like a lattice deformer, making poses or morph targets an "elastic" process. [3]

**[CONTEMPORARY]** Mirai 1.1 added skeletal-animation support for magnet operations, squash/stretch, root rotation and deformer display options. [5]

**[DESIGN/FUTURE]** Our long-term architecture must not make it impossible to edit the control mesh while higher-level deformation data remains valid. Full rigging/morph support is not V1, but stable topology/element identity must anticipate it.

---

# 9. Camera / Viewport

**[CONTEMPORARY]** The 1999 review says clicking in the geometry view can switch to camera mode, where actions change the viewpoint; clicking geometry returns to object editing. [2]

**[CONTEMPORARY]** Mirai 1.1 explicitly included improved camera manipulation. [5]

**[DESIGN]** V1 camera requirements: perspective, orthographic, front/back, left/right, top/bottom, axis snapping, orbit/tumble, pan/track and zoom. Exact historical mouse mapping remains open.

---

# 10. History / Editor Linking

**[CONTEMPORARY]** The 1999 review's "3D operating system" description explicitly says changes in one module propagate to dynamically linked modules. [2]

**Open questions:**

- Was undo operation-based or snapshot-based?
- Were selections included in history?
- How did linked editors participate in undo?
- How were derived surfaces and deformations handled during undo?
- How were topology changes reconciled with morph/animation data?

**[DESIGN]** Mirai-Bastel should eventually have a command/operation layer independent of UI input, giving us reliable undo/redo and future scripting.

---

# 11. N-World → Mirai

N-World is the immediate technical ancestor of Mirai. The surviving historical page says S-Graphics was reworked as N-World and then Mirai and links the N-World 3.0 documentation. [1]

Secondary references list major N-World components including N-Geometry, N-Dynamics, N-Render, N-Paint and game tools. [7]

**Important:** N-World is a technical ancestor, not proof that every feature behaved identically in Mirai. Mirai-specific claims should be confirmed with Mirai-era evidence where possible.

---

# 12. Current Conclusions

## Strongly supported

- Integrated 2D/3D/editor architecture.
- Context- and sequence-driven mouse interaction.
- Selection strongly affects available actions.
- Extensive polygon/subdivision modeling.
- Explicit Volume Modeling / Derived Surface concept.
- Magnet Move with normal-direction falloff.
- Edge-loop-oriented character modeling.
- Integrated paint, animation and deformation capabilities.
- Winged Edge identified by Bay Raitt as the modeller's data structure.

## Still open

- Exact selection gestures and modifier semantics.
- Exact LMB/MMB/RMB mapping by context.
- Exact topology operations and terminology.
- Exact subdivision algorithm and extraordinary-vertex handling.
- Exact Magnet falloff implementation.
- Exact morph/rig/deformation persistence rules.
- Exact undo/history architecture.
- Exact editor-linking/data-sharing architecture.

## Next target: N-World 3.0 documentation

Dissect chapter-by-chapter:

1. Geometry / selection
2. Modeling operations
3. View / camera
4. Dynamics / animation
5. Paint / materials
6. Scripting
7. Data/object concepts
8. Interaction/mouse conventions

---

# Sources

[1] Symbolics S-Graphics/Nichimen N-World/Izware Mirai Information Site  
https://s-graphics.neocities.org/

[2] Jeffrey Abouaf, **Nichimen's Mirai**, Game Developer Magazine, December 1999.  
https://valvearchive.com/archive/Other%20Files/Publications/The%20Cabal%20%28Ken%20Birdwell%29/The%20Cabal%20%28Valve%27s%20Design%20Process%20For%20Creating%20Half-Life%29/Game%20Developer%20Magazine/GDM_December_1999.pdf

[3] Same contemporary Mirai review, modeling/subdivision/animation sections. Mirror:  
https://mirror.kaetemi.be/gdmag/Game%20Developer%20Magazine/Magazines/1999/GDM_December_1999.pdf

[4] WinWorld community discussion, **Request: Mirai and Nendo**, including later user reports.  
https://forum.winworldpc.com/discussion/12264/request-mirai-and-nendo/p2

[5] Daniel Muebner, **New Products: Mirai 1.1**, Game Developer Magazine, April 2000.  
https://media.gdcvault.com/GD_Mag_Archives/GDM_April_2000.pdf

[6] Bay Raitt professional profile.  
https://www.linkedin.com/in/bay-raitt-2204161/

[7] N-World overview / references to N-World 3.0 documentation.  
https://en.wikipedia.org/wiki/N-World
