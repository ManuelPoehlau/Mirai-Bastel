# Documentation

This directory contains the durable project knowledge that should survive individual conversations and AI sessions.

## Start here

| Area | Purpose |
|---|---|
| [Atelier](ATELIER.md) | Artist-Übersicht: Stand, offene Verdikte, nächste Kandidaten (Index, Deutsch) |
| [Roadmap](architecture/ROADMAP.md) | Canonical roadmap and work packages |
| [Architecture](architecture/README.md) | Current system boundaries, accepted architectural direction and V1 decisions |
| [Design](design/README.md) | Interaction and workflow principles, including the current Production GUI inventory |
| [Rendering Vision](design/RENDERING_VISION.md) | Proposed Artist-first character Lookdev direction: eyes, light, reflections, skin, shadows, realtime and final rendering |
| [LookDev Room P2 proposal](design/LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19.md) | PROPOSAL (2026-11-19): LookDev Room for the whole character (room, materials, eye pass LookDev variant, linear colour, studio lighting, stages M1/LD-1 … P5, decisions LD-D1 … LD-D16; **LD-D1 … LD-D14 decided 2026-11-19**); [technical appendix](design/LOOKDEV_P2_TECHNICAL_APPENDIX_2026-11-19.md); architecture draft [AD-038](architecture/AD-038-LOOKDEV-ROOM-M1.md) (ACCEPTED 2026-11-19; LD-1 built 2026-11-19, measured on the reference PC 2026-11-20: LD-D10 and E16 met; LD-2 built 2026-11-21, §18: `SceneObject.look` v15, `view.lookdev`, „Bild speichern“; practical test next; P3 before LD-3 since 2026-11-21, proposal §0.1); P3 architecture [AD-039](architecture/AD-039-LOOKDEV-P3.md) (ACCEPTED 2026-11-22: slices S1 shadow map … S7 maps, P3-0 probe `probe_lookdev.py --p3` complete; **S1 built 2026-11-22**, §16; **S2 built 2026-11-22**, §17: the eyes in the key's shadow; **S3 built 2026-11-23**, §18: dual-lobe specular; **S4 built 2026-11-23**, §19: backscatter with thickness; **S7 built 2026-11-24** ahead of S5 / S6, §20: roughness / normal / translucency maps as paths on the material, scene format v16; **S5 built 2026-11-24**, §21: the studio's prefiltered environment cube (GPU prefilter, read back and uploaded); **S6 built 2026-11-24**, §22: region materials - a LookDev material per face region on the object (LD-D8 „A, Regionen wie vorgeschlagen“, `SceneObject.look_regions`, scene format v17; **S8 „Weiches Licht“ built 2026-11-24**, §23: each light's size as a finite emitter in the diffuse term, default off, after the [diffuse area-light assessment](research/LOOKDEV_DIFFUSE_AREA_LIGHT_TERMINATOR_ASSESSMENT_2026-11-24.md); §23.7: [PCSS assessment](research/LOOKDEV_PCSS_KEY_SHADOW_ASSESSMENT_2026-11-24.md) for the soft key's cast shadow, prototype only; reference PC 2026-11-24: 3-12x over budget, not built as is; the cost diagnosis shows the pass is ALU-bound, the cheapest form +2.6-3.3 ms in the close-up; Manu chose quality over 30 fps: **S9 „Weicher Schatten“ built 2026-11-24**, §24, default off, practical test and probe row open); reference-PC runs and practical tests open; P3 complete, LD-3 next); LD-3 quality manager [AD-040](architecture/AD-040-LOOKDEV-LD3-QUALITY.md) (ACCEPTED 2026-11-25; **LD-3a built 2026-11-25**, §14: block „Qualität“ - Auto / Hoch / Mittel / Entwurf, „In Ruhe verfeinern“ with idle Hoch / Maximal, activity state from a frame signature, GPU timer, a machine setting in `~/.mirai_bastel`; no shader change; reference-PC run §11.1 (also AD-039's S1–S9 run) and practical test §14.5 open; LD-3b after its probe) |
| [Likeness camera proposal](design/LIKENESS_CAMERA_ARCHITECTURE_UX_PROPOSAL_2026-11-27.md) | PROPOSAL (2026-11-27): likeness cameras with a physical lens (focal length, sensor, fit → the one camera's FOV), a reference photo per camera as a screen-space backdrop behind / in front of the model, comparison views, manual then landmark matching, the „Kameraansicht“ as a view state (not a room), slices M1 … M5, decisions LC-D1 … LC-D10 (LC-D1, LC-D3, LC-D4, LC-D5 decided 2026-11-27, §0; the rest open); M1 architecture in [AD-042](architecture/AD-042-LIKENESS-CAMERA-M1.md) (ACCEPTED 2026-11-27, **M1 built** 2026-11-27, §17) |
| [Rendering Research](research/RENDERING_TECHNOLOGY_RESEARCH.md) | Technical landscape, Wētā / SH research, current Mirai baseline, external renderers, open-source references and open questions |
| [GUI Bestandsaufnahme](design/GUI_Bestandsaufnahme.md) | Current, dated GUI state assessment for Modelling, Morph and Rig (2026-11-03; hypotheses are not decisions) |
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
| [WP_INSET_BEVEL_SLIDE.md](WP_INSET_BEVEL_SLIDE.md) | Gebaut 2026-10-29 (`PROVISIONAL`, Grundfunktion): Inset (`I` im Face-Modus), Bevel/Chamfer für Kanten und Punkte (`Ctrl+B`), Vertex Slide (`G` im Vertex-Modus); Entscheidungen, Nicht-Scope, Praxistest B25 |
| [WP_GOZ_P2_PLAN.md](WP_GOZ_P2_PLAN.md) | ZBrush-Brücke P2 (erledigt, Praxistest bestanden 2026-11-06): Polygruppen ↔ Regionen (P2a, E2 erledigt), N-Gons (P2b) (nur in der Datei zerlegt, möglichst Vierecke); Manus Entscheidungen, PC-Test E2, Akzeptanz |
| [WP_GOZ_P3_PLAN.md](WP_GOZ_P3_PLAN.md) | ZBrush-Brücke P3 (gebaut 2026-11-06, Layer-Weg + Praxistest offen): UVs (mit übernehmen), Textur zurück (Kopie neben der Szene), Morph-Targets (Basis + Targets, als ZBrush-Layer falls möglich); PC-Test E3 |
| [WP_DYNAMIC_ORBIT_FOCUS.md](WP_DYNAMIC_ORBIT_FOCUS.md) | Gebaut 2026-11-08 (`PROVISIONAL`): Orbit um den zuletzt bearbeiteten Bereich (ZBrush-artig), getrennt vom Working Pivot; Blender-Recherche, Architektur-Audit, Entscheidungen P1–P9, Praxistest offen |
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
