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

## WP-04 working set (production foundation

| Document | Purpose |
|---|---|---|
| [WP-04_GATE_PLANNING.md](WP-04_GATE_PLANNING.md) | Gate-Plan + Akzeptanzkriterien |
| [WP-04_OPEN_QUESTIONS.md](WP-04_OPEN_QUESTIONS.md) | Offene Entscheidungen Q1–Q4 |
| [WP-04_PRODUCTION_FOUNDATION_DISCOVERY_REPORT.md](WP-04_PRODUCTION_FOUNDATION_DISCOVERY_REPORT.md) | Repository-Analyse, Produktions-Boundaries, Extraktionspfade |
| [WP-04_AGENT_VERIFICATION_REPORT.md](WP-04_AGENT_VERIFICATION_REPORT.md) | Agent-Verifikation, Test-Inventar, Teststrategie, Aufgabenteilung Agent/Claude/Manuel |
| [WP-04_PRE_IMPLEMENTATION_CONSISTENCY_AUDIT.md](WP-04_PRE_IMPLEMENTATION_CONSISTENCY_AUDIT.md) | Gate-für-Gate-Konsistenz-Audit (12→2) gegen Repo-Stand, Amendment/ADRs und Viewport-V0.2-Architektur |

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
