# Mirai-Bastel V1 Core Architecture — Draft 0.1

> **Status:** Working draft — architecture review required
>
> **Purpose:** Define the smallest stable foundation for a Mirai-inspired, modern, extensible 3D modeling environment.

## 1. Vision

Mirai-Bastel is **not** intended to be a literal recreation of Mirai, N-World, or Weta's internal tools.

The historical systems are our research source and inspiration. V1 should capture the qualities that made the workflow powerful:

- direct manipulation
- context-sensitive interaction
- very fast modeling feedback
- topology-aware editing
- selection as a first-class concept
- soft influence rather than a separate modeling mode
- camera interaction that does not fight the modeling workflow
- a live model that can be edited while other systems eventually operate on it
- an architecture that remains open and extensible

The long-term goal is a **living 3D system**: a small stable core surrounded by extensions, tools and eventually AI-assisted development.

## 2. Core Principles

### 2.1 Small core, open doors

V1 must not become a miniature Blender. The core should contain only infrastructure that many systems depend on.

Candidate core responsibilities:

- scene ownership
- mesh/topology data
- stable element identity
- selection
- operations/commands
- undo/redo history
- events/change notifications
- serialization foundations
- extension API foundations

Rendering, UI widgets, individual modeling tools and future animation/rigging systems should not become tightly coupled to the core.

### 2.2 UI is a client of the core

The core must not depend on pyglet, OpenGL, Qt, or any particular UI toolkit.

Conceptually:

```text
Input / UI / Viewport
        |
        v
Interaction / Tool layer
        |
        v
Operations / Commands
        |
        v
Domain model / Core
        |
        v
History + Change Events
```

The UI observes the state; it should not own the authoritative mesh state.

### 2.3 Operations instead of arbitrary mutation

Model changes should normally happen through explicit operations/commands rather than scattered direct mutations.

Example:

```text
User gesture
    -> MoveVerticesOperation
        -> apply(mesh, selection, parameters)
            -> change event
            -> history entry
            -> viewport update
```

This gives us a foundation for:

- undo/redo
- repeatable operations
- macros
- scripting
- replay/debugging
- AI-generated operations
- future collaboration

### 2.4 Stable identity

Vertices, edges and faces should have stable IDs rather than being identified solely by list indices.

The exact storage strategy remains open, but the public domain model should conceptually expose:

```text
VertexId
EdgeId
FaceId
```

This is especially important when topology changes.

## 3. V1 Domain Model

The initial domain model is deliberately small:

```text
Scene
  |
  +-- Mesh
       |
       +-- Vertices
       +-- Edges
       +-- Faces
       +-- Topology relations
```

### Vertex

At minimum:

- stable ID
- position
- topology references as required by the chosen data structure

### Edge

At minimum:

- stable ID
- endpoint relationships
- adjacent topology relationships

### Face

At minimum:

- stable ID
- boundary/topology relationships
- normal/derived geometric information where appropriate

### Mesh

The mesh owns topology and geometric data. It should provide controlled operations for querying and changing topology rather than exposing arbitrary internal containers as the primary API.

## 4. Topology Direction

Historical research strongly suggests that the S-Geometry/N-World/Mirai family relied on rich topology rather than treating a mesh as merely a list of independent triangles/quads.

For V1 we should therefore investigate a **winged-edge / half-edge-like topology representation** before committing to a simple indexed-face structure.

The exact implementation is deliberately undecided in this draft.

Requirements:

- fast vertex/edge/face adjacency
- reliable edge/face traversal
- loop/ring traversal foundations
- topology-safe editing
- stable element identity
- support for quads as first-class modeling surfaces

Do not implement a sophisticated topology structure merely because it is historically authentic. Select the modern representation that gives us the required behavior and future extensibility.

## 5. Selection System

Selection is a **first-class domain concept**, not merely a boolean flag attached to mesh elements.

Initial selection domains:

```text
Vertex
Edge
Face
```

The active selection mode is UI/tool state, while the actual selected element sets belong to the selection system.

Conceptually:

```text
Selection
  +-- vertices: Set<VertexId>
  +-- edges:    Set<EdgeId>
  +-- faces:    Set<FaceId>
  +-- active element / history (if needed)
```

Selection operations should eventually be scriptable and composable.

## 6. Soft Selection / Influence

Soft selection should **not** become a fourth selection mode or a special vertex type.

Instead:

```text
Primary Selection
       |
       v
Influence Calculation
       |
       v
Weights / Influence Map
       |
       v
Transform / Modeling Operation
```

This allows the same influence system to be reused by:

- Move
- Rotate
- Scale
- Tweak
- potentially future deformation operations

V1 only needs a basic distance/topology-aware falloff implementation. The influence system should have a replaceable strategy interface so additional falloff methods can be added later.

## 7. Modeling / Operations

Initial V1 modeling operations should focus on the direct workflow agreed for the project:

- Move
- Rotate
- Uniform Scale
- Axis-constrained Scale
- Tweak
- basic extrusion
- basic inset
- basic topology operations as justified by research
- subdivision / smoothing

The exact operation list should be finalized after the N-World/Mirai research pass.

Operations should receive explicit context rather than reaching into UI globals.

Example conceptual input:

```text
OperationContext
  - scene
  - mesh
  - selection
  - transform space
  - pivot
  - axis constraint
  - influence map
  - interaction parameters
```

## 8. Interaction Layer

The historical Mirai/N-World interaction model is an important research target.

We should avoid designing V1 as a conventional toolbar-first application.

The interaction layer should support:

- hover detection
- selection feedback
- direct mouse manipulation
- modifier keys
- context-sensitive operations
- temporary interaction states
- camera manipulation without losing modeling context

The UI interaction layer translates gestures into explicit operations.

Example:

```text
Hover Vertex
   + Ctrl + drag
       -> Tweak / Move interaction

Selected Edge
   + drag
       -> Edge operation

Selected Face
   + extrude gesture
       -> Extrude operation
```

The exact gesture map is **not frozen yet**. It should be informed by the historical research and practical testing.

## 9. Camera / Viewport

V1 camera support must include the basic workflow already identified:

- perspective
- orthographic
- front
- back
- left/right
- top
- bottom
- axis snapping
- orbit/tumble
- pan/track
- zoom/dolly
- frame selection/object

Camera state belongs to the viewport/presentation layer, not the mesh core.

A viewport may observe the scene and use one or more cameras without changing the underlying scene model.

## 10. Subdivision / Derived Geometry

V1 should distinguish between:

```text
Control Mesh
     |
     v
Derived / Display Surface
```

The control mesh remains authoritative.

Subdivision is initially a display/modeling system rather than a reason to duplicate the authoritative mesh state.

The current prototype contains a simple Catmull-Clark implementation. It is useful as a learning prototype but should not be treated as the final topology architecture.

## 11. History / Undo

Undo/redo is a core architectural concern, not a UI feature to bolt on later.

V1 should investigate a command-based history:

```text
Operation
   -> execute
   -> History Entry
   -> inverse/reversible state
```

The exact mechanism is open:

- inverse operations
- state snapshots
- structural diffs
- hybrid approach

We should choose based on actual mesh editing requirements and memory constraints rather than historical imitation.

## 12. Event / Change System

Core changes should be observable without the core knowing who is observing them.

Potential event categories:

```text
MeshTopologyChanged
MeshGeometryChanged
SelectionChanged
SceneChanged
HistoryChanged
```

The final event model should remain lightweight. Avoid building a giant message-bus framework before it is needed.

## 13. Extension System

Extensibility is a **V1 architectural requirement**, even if the first extension is tiny.

The long-term target is:

```text
Core
  |
  +-- Modeling extensions
  +-- Deformation extensions
  +-- Animation extensions
  +-- Import/export extensions
  +-- Analysis extensions
  +-- UI extensions
  +-- AI extensions
```

Extensions should depend on stable public APIs rather than private implementation details.

The extension mechanism must be simple enough that a developer or AI can create a small tool without modifying the core.

## 14. Scripting / AI Readiness

Python is currently the intended implementation language.

We should preserve the useful architectural idea behind the historical Lisp/CLOS systems: the running application should expose a sufficiently rich, inspectable object model.

Long-term goals include:

- inspect scene objects
- inspect mesh topology
- inspect selection
- query available operations
- execute operations
- create/register extensions
- inspect operation/history state

AI should be treated as a **client of the system**, not as the system's foundation.

A future AI integration should be able to reason over stable APIs rather than manipulating arbitrary UI internals.

## 15. Rendering Boundary

The first prototype uses pyglet/OpenGL legacy-style rendering. This is intentionally disposable.

The core must not depend on OpenGL.

Conceptually:

```text
Core Scene/Mesh
      |
      v
Rendering Adapter
      |
      v
OpenGL / future renderer
```

This allows us to replace the prototype renderer without rewriting modeling logic.

## 16. Serialization

A simple project/scene serialization format should eventually be defined, but V1 should not prematurely lock itself into a complex asset format.

Requirements:

- stable IDs
- scene structure
- mesh topology
- vertex positions
- selection/state where useful
- versioning

The format should be human-inspectable where practical because this benefits debugging, scripting and AI tooling.

## 17. What V1 Explicitly Does NOT Include

Unless research or implementation experience changes the decision, V1 should not attempt to include:

- full animation system
- production rigging
- IK
- skeletal deformation
- full morph-target editor
- materials/shaders system
- advanced renderer
- node-based procedural system
- physics
- compositor
- asset-management suite
- full scripting IDE
- autonomous AI agent inside the application

The architecture should leave room for them without implementing them prematurely.

## 18. Proposed V1 Dependency Direction

```text
                 UI / Viewport
                      |
                 Interaction
                      |
                 Operations
                      |
        +-------------+-------------+
        |                           |
    Selection                    History
        |                           |
        +-------------+-------------+
                      |
                 Scene / Mesh
                      |
                    Core
```

Extensions should consume public Core/Domain/Operation APIs. Core must never import an extension.

## 19. Open Architectural Questions

These are intentionally unresolved until research/review:

1. Winged Edge vs half-edge vs hybrid topology representation?
2. Exact mesh mutation API?
3. Operation object lifecycle?
4. Undo strategy: inverse, snapshot, diff or hybrid?
5. How much state belongs to Selection vs Interaction Context?
6. How should hover state be represented?
7. How should temporary mouse gestures map to operations?
8. How should subdivision-derived geometry be cached?
9. What is the minimum viable extension API?
10. What scripting surface should be public?
11. How should scene serialization be versioned?
12. Which historical Mirai/N-World behaviors should V1 reproduce exactly, and which should merely inspire the design?

## 20. Design Rule for the Project

> **Research first, freeze as little as possible, implement small vertical slices, and keep the core understandable enough that a human or AI can inspect and extend it.**

This document is a proposal, not a specification carved in stone. Claude, Codex/Devin/Cursor, future contributors and later research should be allowed to challenge it.

The architecture is successful if it remains easy to understand and easy to change while the system grows.
