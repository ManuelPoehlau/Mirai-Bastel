# Deformation

Recherche zu Morph Targets, Skinning, Rigging, Deformation und der Idee, ein bereits animiertes/geriggtes Mesh weiter modellierbar zu halten.

- [MESH_ARCHITECTURE_AUDIT_2026-10-27.md](MESH_ARCHITECTURE_AUDIT_2026-10-27.md) — Mesh-Architektur-Audit für Morphing,
  Rigging und Topologie-Änderungen nach Morph Targets (Englisch, Discovery, keine Entscheidung); offene Artist-Entscheidungen
  in Abschnitt H. Artist-seitige Recherche: [CHARACTER_SYSTEMS_RESEARCH.md](../CHARACTER_SYSTEMS_RESEARCH.md).
- [ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md](ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md) — Architektur- und
  Performance-Audit zur Frage „trägt die Architektur ein Basis-Mesh mit etwa 100.000 Flächen auf dem Referenz-PC?“
  (Englisch, Discovery, keine Entscheidung; Kurzfassung für Manu am Anfang). Datenfluss Core → Auswertung → Viewport am
  Code, Messungen bei 20k und 87,5k (Container), Engpässe pro Kostenstelle, Optionen und offene Entscheidungen (§H),
  Messläufe für den Referenz-PC (§J).
