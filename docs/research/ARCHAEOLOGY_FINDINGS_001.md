# Archaeology Findings 001 — N-World / Mirai Interaction Model

**Research date:** 2026-08-25  
**Status:** active research  
**Focus:** reconstructing actual historical behavior from contemporary documentation and descendants.

---

## 1. Major finding: Mirai was designed as an integrated working environment

A December 1999 contemporary review of Nichimen's Mirai describes its environment as being conceived more like a **"3D operating system"** than a conventional application UI.

The review says modules behave like applications, while remaining dynamically linked so changes in one propagate through the others immediately. It gives concrete examples involving multiple geometry editors, 2D/3D paint sessions and UV mapping windows. Different geometry windows could show different objects/sets while sharing the same scene/camera context, and painting changes could propagate to geometry and 3D views.

**Source:** Jeffrey Abouaf, *Game Developer Magazine*, December 1999, "Nichimen's Mirai".

- GDC Vault PDF: https://media.gdcvault.com/GD_Mag_Archives/GDM_December_1999.pdf
- Mirror: https://mirror.kaetemi.be/gdmag/Game%20Developer%20Magazine/Magazines/1999/GDM_December_1999.pdf

**Confidence:** PRIMARY/TIME-CONTEMPORARY PRODUCT REVIEW — very high for the described user-visible behavior.

**Implication for Mirai-Bastel:**

Do not model the eventual application as a modern monolithic "Modeling Mode" plus separate unrelated tools by default. The historical architecture suggests a shared asset/state model with multiple linked editors/views.

---

## 2. Major finding: interaction was deliberately context- and sequence-driven

The same 1999 review describes Mirai's interface as having minimal icons and no tooltips, driven heavily by left/middle/right mouse interaction. The result depends on **sequence and context**. The review explicitly notes that this can initially feel disconcerting, but becomes very fast once the user understands the orders.

This is unusually important because it matches the workflow we are trying to rediscover from the Bay Raitt / Martin Krol videos.

**Confidence:** TIME-CONTEMPORARY PRODUCT REVIEW — high.

**Implication:**

The interaction layer should eventually be treated as a first-class system, not as a collection of arbitrary keyboard shortcuts. A gesture should be interpreted from:

- current editor/context
- hover target
- current selection
- mouse button
- modifier keys
- operation stage/sequence

This is an architectural hypothesis derived from observed behavior, not a claim about the original internal implementation.

---

## 3. Mirai 1.1: Magnet Move with falloff is explicitly documented

A contemporary April 2000 *Game Developer Magazine* product update says Mirai 1.1 added **magnet move**, allowing multiple vertices to be moved along normals with falloff. It also mentions improved camera manipulation and additional modeling options.

**Source:** *Game Developer Magazine*, April 2000, "Nichimen's High Hopes for the Future".

- PDF: https://media.gdcvault.com/GD_Mag_Archives/GDM_April_2000.pdf

**Confidence:** TIME-CONTEMPORARY PRODUCT SOURCE — very high.

**Implication:**

Our concept of soft selection should not be implemented as merely another selection mode. Historically, the influence/falloff mechanism was attached to a modeling operation (magnet move). We should design an influence system that can later be reused by multiple operations.

---

## 4. Mirai's magnet modeling was not merely a generic proportional transform

The December 1999 review gives more detail: magnet moves along face normals with falloff were used to model surface deformations/displacements. The review gives examples such as shaping cheekbones and brows by applying the operation to edge loops, and creating extruded clothing/armor layers.

**Source:** December 1999 *Game Developer Magazine* review.

**Implication:**

A useful Mirai-Bastel abstraction may be:

```text
Selection / seed
      ↓
Influence field / falloff
      ↓
Operation vector / normal / custom axis
      ↓
Deformation
```

rather than baking falloff logic directly into "Soft Select" UI.

---

## 5. Subdivision was a central polygonal strategy

The December 1999 review explicitly describes Mirai as a polygonal modeler and says Nichimen had embraced subdivision-mesh modeling as its approach to producing smooth organic surfaces. It contrasts this with NURBS, B-splines and H-splines.

The same article contains a figure showing a high-resolution character and morph targets.

**Confidence:** TIME-CONTEMPORARY PRODUCT REVIEW — high.

**Implication:**

The control mesh / derived smooth surface relationship should be treated as a core concept, not merely a render-time optional effect.

---

## 6. N-World was a suite, not merely a mesh editor

Historical references consistently identify separate components in N-World, including:

- **N-Geometry** — polygon modeling, smoothing, magnet geometry editing, instancing
- **N-Dynamics** — animation scripting, curve-based animation, skeletal animation
- **N-Render** — surfacing/rendering, including ray tracing
- **N-Paint** — 2D/3D painting and related tools
- game-specific tools/exporters

The historical S-Graphics/N-World/Mirai information site states that S-Graphics was an integrated 2D/3D graphics suite and that the system was later reworked as N-World and Mirai.

**Sources:**

- https://s-graphics.neocities.org/
- https://en.wikipedia.org/wiki/N-World (secondary index; useful primarily for pointers to original sources)
- https://nekonomicon.irixnet.org/forum/users/SiliconClassics/3.html (historical community archive; secondary)

**Confidence:** mixed; individual feature claims vary by source. The existence of the suite architecture is strongly supported.

**Implication:**

The eventual Mirai-Bastel architecture should leave room for shared scene/asset state and multiple editors rather than hard-coding a modeling-only application.

---

## 7. The N-World → Mirai → Nendo → Wings lineage is technically useful

The N-World historical record identifies the winged-edge modeler as the basis that inspired Nendo, which in turn inspired Wings3D. This makes Wings3D unusually valuable as a surviving descendant for reconstructing interaction patterns where Mirai's original manuals are unavailable.

This is not proof that every Wings feature existed in Mirai. It is a **comparative reconstruction tool**.

**Important rule:**

> Wings behavior can corroborate a hypothesis, but cannot by itself establish a Mirai fact.

---

## 8. Strong concrete descendant evidence: Wings preserves a Mirai camera mode

The Wings3D 1.6.1 manual explicitly documents selectable camera modes for **Mirai, Nendo, Maya, 3ds Max and Blender**.

Its Mirai camera description says:

- MMB click/release enters rotate mode
- MMB scroll wheel zooms
- arrow keys translate the view
- RMB restores the original view before tumbling
- Q toggles rotate/translate while in rotate mode

A Wings3D forum explanation from 2012 gives an even more explicit interaction sequence for Mirai camera mode:

- MMB starts camera mode
- LMB accepts new camera coordinates
- Q switches between tumble and track
- MMB hold performs dolly/zoom while camera mode is active

**Sources:**

- Wings3D Manual 1.6.1: https://www.cs.usfca.edu/~wells/3DCG/Model-Render%20stuff/Wings%20stuff/wings3d_manual1.6.1.pdf
- Wings3D forum: https://www.wings3d.com/forum/showthread.php?mode=linear&pid=937&tid=122

**Confidence:** HIGH for Wings' documented Mirai-compatible camera mode; MEDIUM for using this as evidence of original Mirai behavior.

**Implication:**

Our planned camera system should support an explicit **camera interaction state**, rather than treating orbit/pan/zoom as permanently active mouse gestures.

---

## 9. Wings Tweak + magnets shows a likely surviving interaction pattern

The Wings3D 1.6.1 manual documents Tweak as a dedicated modeling mode:

- LMB: drag vertices freely
- RMB: exit Tweak
- MMB: tumble
- Shift+MMB: track
- Ctrl+Shift+MMB: dolly
- `1`: toggle magnets
- `+/-`: change falloff

It also documents vector + magnet operations and advanced context-sensitive menus.

**Sources:**

- Wings3D Manual 1.6.1: https://www.cs.usfca.edu/~wells/3DCG/Model-Render%20stuff/Wings%20stuff/wings3d_manual1.6.1.pdf
- Wings3D documentation: https://en.wikibooks.org/wiki/Wings_3D/User_Manual/Vertex_Operations_with_Advanced_Menus

**Important:** This is Wings3D documentation, not direct Mirai documentation. It is useful as a descendant/reference implementation of the interaction philosophy.

**Implication:**

The eventual Mirai-Bastel Tweak system can plausibly be designed as a temporary interaction context in which viewport navigation remains accessible without leaving the modeling operation.

---

## 10. A particularly useful architectural clue: secondary selections

Wings3D's advanced vertex-operation documentation describes **secondary selections** used to define custom vectors, axes, origins and other operation parameters. Magnet operations can be accessed as part of these advanced commands.

This suggests a broader interaction pattern worth investigating historically:

```text
Primary selection
      ↓
secondary/contextual selection
      ↓
operation parameters
      ↓
execute
```

This is extremely close to the idea of a modeling system where the user can establish a direction, origin, falloff or reference directly in the viewport rather than opening a modal property panel.

Again: this is evidence from Wings, not proof of Mirai internals.

---

## 11. Historical software archaeology target identified

The historical S-Graphics/N-World/Mirai site explicitly links to **N-World 3.0 Online Documentation**. Multiple independent secondary sources still point to the same original URL:

`http://www.aaronjamesrogers.com/misc/nworld/N-World-Intro.html`

The original host is currently difficult/unreliable to retrieve, but the repeated references establish a concrete archival target rather than a vague rumor that documentation once existed.

**Sources:**

- https://s-graphics.neocities.org/
- https://handwiki.org/wiki/Software%3AN-World
- https://ultimatepopculture.fandom.com/wiki/N-World

**Next archaeology actions:**

1. Search Wayback Machine snapshots of the exact URL.
2. Search archived subpages from the same `/misc/nworld/` path.
3. Search the exact filenames/titles in web indexes.
4. Search downloadable N-World/Mirai distributions for bundled HTML/help files.
5. Search old SGI/IRIX community archives for documentation mirrors.
6. Compare documentation screenshots against surviving software screenshots.

---

# Current reconstructed model

At this point the evidence supports the following **working model**:

```text
                         SHARED ASSET / SCENE STATE
                                   │
             ┌─────────────────────┼─────────────────────┐
             │                     │                     │
       Geometry Editor        Animation/IK          Paint/UV/etc.
             │                     │                     │
             └─────────────────────┼─────────────────────┘
                                   │
                            shared live updates
                                   │
                         ┌─────────┴─────────┐
                         │                   │
                    Control Mesh       Derived Surface
                         │                   │
                         └────── SubD ──────┘
                                   │
                           Modeling Operations
                                   │
                  ┌────────────────┼────────────────┐
                  │                │                │
               direct           vector          magnet/
               transform        operation       influence
```

This is **our reconstructed conceptual model**, not a claim that this exact software architecture existed internally.

The next major goal is to replace conceptual reconstruction with **direct N-World documentation evidence** wherever possible.

---

# Research principle

We should preserve historical facts even when they contradict our initial assumptions.

**Do not retrofit Mirai to our V1 design.**

First reconstruct what it actually did.

Then decide what to keep, modernize, simplify or deliberately reinvent.
