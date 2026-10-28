# Documentation

This directory contains the durable project knowledge that should survive individual conversations and AI sessions.

## Start here

| Area | Purpose |
|---|---|
| [Atelier](ATELIER.md) | Artist-Übersicht: Stand, offene Verdikte, nächste Kandidaten (Index, Deutsch) |
| [Roadmap](architecture/ROADMAP.md) | Canonical roadmap and work packages |
| [Architecture](architecture/README.md) | Current system boundaries, accepted architectural direction and V1 decisions |
| [Design](design/README.md) | Interaction and workflow principles |
| [Future Ideas](future_ideas/README.md) | Ideas and requirements deliberately deferred from implementation |
| [Research](research/README.md) | Historical and technical investigation |
| [Archive](archive/README.md) | Historical reviews and superseded working material |
| [Viewport](viewport/VIEWPORT_V02_ARCHITECTURE.md) | Viewport v0.2 architecture (binding spec of `src/viewport`) and research (`viewport/`) |
| [Reusable Development Prompts](DEVELOPMENT_PROMPTS.md) | General prompts for recurring software-development tasks across projects |

## Important distinction

Not every document is a current specification.

- **Canonical documents** describe the current accepted state.
- **Design documents** describe intended interaction and UX principles.
- **Future Ideas** preserve deliberately deferred ideas.
- **Research** records evidence and investigation.
- **Archive** preserves historical reasoning without competing with current decisions.

When documents overlap, the canonical document wins. Other documents should link to it rather than silently maintaining a second version.

## Archived work packages and audits (2026-10-21)

WP-04 (Production foundation, Gates 1–7 — done, see [ROADMAP](architecture/ROADMAP.md)), the early WP-01/WP-02 packages
and the September audits were moved out of the docs root into [archive/early_work_packages/](archive/early_work_packages/)
and [archive/audits_2026-09/](archive/audits_2026-09/). They are project memory, not current guidance.

## Consolidation (2026-10-24)

The Playground, the Symmetry / SubD / Shading Labs and the experiments whose results are in `src/` were removed (list
and last commit: [experiments/README.md](../experiments/README.md)). Their docs, the finished Claude Code handoffs from
`architecture/` and the Playground design docs are in [archive/experiments_2026-10/](archive/experiments_2026-10/) and
[archive/handoffs_2026-10/](archive/handoffs_2026-10/).

## Work Packages

| Document | Purpose |
|---|---|
| [WP_DELETE_DISSOLVE_PLAN.md](WP_DELETE_DISSOLVE_PLAN.md) | Delete (destruktiv) / Dissolve (bewahrend) auf Vertex-/Edge-/Face-Ebene, Production-first ohne Lab; Status, offene Fragen und Praxis-Check am Ende |
| [WP_PLAYGROUND_TOOLS_PROMOTION.md](WP_PLAYGROUND_TOOLS_PROMOTION.md) | Box/Paint Select, Tweak und Loop-Werkzeuge aus dem Playground in die App (2026-10-15); Nachtrag 2026-10-28: Achse einmalig, Tweak = Halte-Geste, Ctrl+LMB-Ziehen entfernt, kleineres Gizmo: Manus Entscheidungen, Annahmen, Praxistest |
| [WP_TOOLBOX_GAPS_PLAN.md](WP_TOOLBOX_GAPS_PLAN.md) | Geplant 2026-10-23: Collapse V/E/F, Select Through, Transform-Raum World/Normal, Grow/Shrink, Loop-Extend, Next/Prev Loop, Relax/Smooth, Subdivide — Pakete A/B/C, Slices, Tasten, Praxistest |
| [WP_ORTHO_VIEWS_PLAN.md](WP_ORTHO_VIEWS_PLAN.md) | Gebaut 2026-10-28 (`PROVISIONAL`): Ortho/Persp (`U`), Standardansichten per Shift beim Orbit, Working Pivot rastet auf die Symmetrieebene (Manus V-1..V-3); Ergebnis und Praxistest B23 |

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
