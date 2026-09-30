# Topology

Recherche zu Winged Edge, Half Edge, Face-Vertex-Meshes und anderen Datenstrukturen für interaktives Modeling.

## Dokumente

- [`CONNECT_EDGES_SPEC.md`](CONNECT_EDGES_SPEC.md) — Verhaltensvertrag Connect Edges; §11 Praxisbefunde (2026-09-21)
- [`CONNECT_NONQUAD_DISCOVERY.md`](CONNECT_NONQUAD_DISCOVERY.md) — Discovery: Nicht-Quads, Eck-Verbindungen, Fortsetzen (keine Entscheidung)
- [`KNIFE_FACE_CUT_DISCOVERY.md`](KNIFE_FACE_CUT_DISCOVERY.md) — Discovery: Knife schneidet in Faces (Face Cut) — Referenzen, Topologie-Fälle, Core-Optionen, Lab-Varianten, Artist-Test (keine Entscheidung); Probe `experiments/topology/knife_face_cut_probe.py`
- [`FACE_HOLES_DISCOVERY.md`](FACE_HOLES_DISCOVERY.md) — Discovery: geschlossene Form in einer Face — Faces mit Löchern (Silo/Maya) vs. Bridges (Blender/Wings), Impact-Inventar, Optionen H0–H5, Artist-Fragen (keine Entscheidung); Probe `experiments/topology/face_holes_probe.py`
- [`KNIFE_CROSS_FACE_DISCOVERY.md`](KNIFE_CROSS_FACE_DISCOVERY.md) — Discovery: ein Knife-Segment über mehrere Faces (Q5) als Segment-Auflösung im einen Knife — Referenzlücken Blender/Wings, Walk vs. Plane, Kamera-Abhängigkeit, Fälle, Lab-Varianten auf D, Artist-Test (keine Entscheidung); Probe `experiments/topology/knife_cross_face_probe.py`
- [`ONE_KNIFE_PROMOTION_DISCOVERY.md`](ONE_KNIFE_PROMOTION_DISCOVERY.md) — Architecture Gate: ein Knife aus Production-Knife und Q5 — Parity-Matrix, Session-Modell A/B/C, Core (B2b vs. B2c), R3/R5, Capability vs. UX, Migrationsoptionen mit Empfehlung (Vorschlag, keine Entscheidung); Probe `experiments/topology/one_knife_parity_probe.py`

Der aktive Topologie-Experimentplan liegt unter [`experiments/topology/TOPOLOGY_EXPERIMENT_PLAN.md`](../../../experiments/topology/TOPOLOGY_EXPERIMENT_PLAN.md).
