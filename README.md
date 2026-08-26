# Mirai-Bastel

A modern, experimental 3D authoring system inspired by the ideas and workflow of Mirai / N-World.

## The important distinction

The first practical milestone is a small, intuitive polygon modeler.

**That is intentionally where we start — it is not where the project ends.**

The modeler is the first visible part of a larger system, similar in spirit to how Mirai was one part of the broader N-World environment. The long-term goal is a flexible, persistent 3D environment in which modeling, topology, deformation, rigging, animation, scripting and other tools can exist as cooperating parts of the same system.

We are not trying to recreate the original Mirai source code or reproduce its historical implementation. We are interested in understanding the ideas, workflows and architectural principles that made systems like Mirai/N-World special — and exploring how those ideas could be rebuilt with modern technology.

A particularly important inspiration is the integrated workflow:

```text
model
  ↓
rig
  ↓
test deformation
  ↓
back to modeling
  ↓
change topology
  ↓
continue working with the rest of the scene
```

The goal is not to pretend that topology changes, skin weights and morph data are magically trivial. The goal is to build a Core architecture that can eventually support this kind of workflow rather than forcing modeling, rigging and animation into completely separate worlds.

## Architecture principle

> **Implement little. Assume much.**

We deliberately keep individual milestones small, while taking known future requirements into account when defining architectural boundaries.

This does **not** mean building a huge framework before we have a working application.

It means avoiding decisions that would make already-known future goals unnecessarily expensive to add later.

Versions are milestones, not separate products:

```text
V1 → V2 → V3 → ...
```

There is no planned "finished version". The system is expected to remain alive and extensible.

## Current status

The first Core V1 milestone is complete and has been validated through its automated test suite and review process.

A separate `experiments/mirai_bastel_viewport_V1/` Praxistest has also been completed. It connects the V1 Core to a minimal real-time OpenGL viewport and was tested on real hardware. The experiment validated the basic Scene → Mesh → Selection → Move → Commit → History → Undo/Redo path together with camera interaction.

The viewport experiment remains deliberately under `experiments/`. It is a reference/prototype, not yet the architecture of the production application.

The next development step is therefore **architectural consolidation**: determine the production `src/` boundaries from the lessons of the Core and Viewport experiments before building the actual application structure.

## Current V1 direction

The first useful application is intended to become a small, direct polygon/subdivision modeler, roughly in the spirit of Silo/Wings3D, combined with interaction ideas that make Mirai especially interesting to us.

The eventual modeler focus includes:

- Vertices / Edges / Faces
- intuitive component selection
- Hover interaction
- Translate / Rotate / Scale
- Tweak
- Soft Selection
- basic topology operations
- subdivision
- perspective / orthographic views
- Front / Back / Left / Right / Top / Bottom snapping
- clean and topology-safe mesh data structures

Not all of these are implemented in the current V1 milestone. They describe the intended direction, while individual milestones remain deliberately small.

## Future system areas

The eventual system may grow to include:

- persistent Scene / Core model
- advanced topology
- subdivision surfaces
- morph targets
- deformation
- rigging / skeletons
- animation
- materials / shading
- scripting and extensions
- AI-assisted inspection and authoring
- additional tools and workflows

These are future areas, not automatic V1 requirements. Their existence must nevertheless be considered when defining Core boundaries so that known future goals are not accidentally made unnecessarily expensive.

For smaller ideas and observations that should not be forgotten, see `docs/future_ideas/`.

## Historical research

A significant part of the project is technical archaeology into Mirai, Nendo, N-World and related systems.

Rather than relying only on nostalgia or second-hand descriptions, we collect historical documentation, technical material, demonstrations, articles and other primary or near-primary sources.

The goal is to extract the underlying systems and workflows, for example:

```text
Selection
Mouse Interaction
Modeling
Camera
Topology
Subdivision
Animation / Morph
History / Editor
Scripting / Extensibility
```

We then compare those ideas with modern approaches and decide deliberately what should be recreated, modernized, simplified or left behind.

The project is therefore both an implementation experiment and a technical archaeology project.

## Why "Bastel"?

Because this started as a spontaneous:

> "What if I finally built my own Mirai?"

project. 😁

And because this is supposed to remain a place for experimentation, research and ideas — not a corporate product roadmap.

## Documentation

The `docs/` directory contains the evolving project vision, architecture decisions, historical research and other material that should remain available to both humans and AI collaborators.

Important architectural decisions are deliberately recorded as they are made. This is part of the project's workflow: fresh reviews and independent AI perspectives should be preserved rather than relying on a long conversation to retain the reasoning.

## Repository structure

```text
src/          Production application code (currently Core baseline only)
experiments/  Isolated milestones, prototypes and practical tests
tests/        Repository-level tests
docs/         Architecture, research, workflow and future ideas
examples/     Small usage examples
references/   External/reference material kept with the project
```

Nothing here should be considered final. The system is expected to evolve as we learn more from historical systems, modern software and our own experiments.
