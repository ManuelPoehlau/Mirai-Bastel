# Subdivision

Technische und artist-seitige Recherche zu Catmull-Clark und verwandten Subdivision-Verfahren.

**Entschieden (nicht hier):** Das Control Mesh ist autoritativ; die abgeleitete Fläche ersetzt es nie
(`docs/V1_SPEC.md` §11, `docs/architecture/V1_CORE.md` §10).

## Dokumente

- [SUBDIVISION_SURFACES_RESEARCH.md](SUBDIVISION_SURFACES_RESEARCH.md) — Research V1 (2026-10-02, Discovery, keine
  Entscheidungen): Artist-Intent-Modelle (Vorschau, Käfig + live, auf der Fläche greifen, Backen, teilweise),
  Algorithmenraum (Catmull-Clark, Ränder, Pole, Creases, Grenzfläche), OpenSubdiv vs. eigene Implementierung,
  Sandbox-Messungen und Budget für die Referenz-Hardware, Viewport (Käfig, Normalen, Picking), Wechselwirkungen
  (Topologie-Operationen, Symmetrie, Undo, Deformationskette), DCC-Vergleich, vorbereitete Artist-Tests.
- Lab: [`experiments/subdivision_lab/`](../../../experiments/subdivision_lab/README.md) (WP-SUBD-LAB-01 Slice 1) — macht
  T-SUBD-1 und T-SUBD-2 spielbar. Stand: gebaut, nicht Artist-validiert.

## Verwandt (nicht duplizieren, verlinken)

- `docs/research/MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §4.4, §7, §15.7 — Pole, Literatur, Kontrollmesh + SubD-Vorschau
- `docs/research/MIRAI_SYSTEMS.md` §6, `MIRAI_SYSTEMS_1999.md` §7 — Mirai Volume Modeling / Derived Surface
- `docs/research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md` — Subdivision Shading dort bewusst zurückgestellt
- `docs/research/symmetry/` — SubD × Spiegelnaht
- `docs/research/topology/FACE_HOLES_DISCOVERY.md` — Löcher sind für SubD nicht definiert
