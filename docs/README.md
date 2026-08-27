# Documentation

This directory contains the durable project knowledge that should survive individual conversations and AI sessions.

## Start here

| Area | Purpose |
|---|---|
| [Architecture](architecture/README.md) | Current system boundaries, accepted architectural direction and V1 decisions |
| [Design](design/README.md) | Interaction and workflow principles |
| [Future Ideas](future_ideas/README.md) | Ideas and requirements deliberately deferred from implementation |
| [Research](research/README.md) | Historical and technical investigation |
| [Archive](archive/README.md) | Historical reviews and superseded working material |

## Important distinction

Not every document is a current specification.

- **Canonical documents** describe the current accepted state.
- **Design documents** describe intended interaction and UX principles.
- **Future Ideas** preserve deliberately deferred ideas.
- **Research** records evidence and investigation.
- **Archive** preserves historical reasoning without competing with current decisions.

When documents overlap, the canonical document wins. Other documents should link to it rather than silently maintaining a second version.

## For AI collaborators

Start with this index when a task crosses repository areas, then follow the nearest local README. The repository root `AGENTS.md` defines the documentation and collaboration rules that apply to all agents.

The intended information flow is:

```text
Research / Experiment
        ↓
Observation / Review
        ↓
Assessment / Decision
        ↓
Canonical documentation
        ↓
Implementation
```
