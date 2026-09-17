"""PlaygroundPygletStore — echtes GL-Backend für den Playground-Renderer.

AD-010 (`docs/architecture/AD-010-PLAYGROUND-SUPERSEDES-LAB-BINDING.md`):
Der Playground-Viewport läuft im Live-Fenster (echter GL-Kontext) über
`PygletStore` statt `TraceStore`. Referenz- und Beweis-Implementierung ist
`LabPygletStore` in
`experiments/mirai_bastel_integration_lab/adapters/core_to_render.py`
(WP-IL-01, real-GL-live-verifiziert) — hier als eigene Playground-Klasse
adaptiert statt cross-experiment importiert: `playground/` konsumiert
bewusst keinen Code aus `experiments/` (AGENTS.md §M3 Promotion Boundary
gilt sinngemäß auch für diese Richtung — Experimente bleiben Spielwiese,
kein Playground-Abhängigkeitsziel).

Grund für das Padding (identisch zur Lab-Begründung, siehe
`viewport.resource_store.PygletStore`-Docstring "Scope-Grenze"): Production
`PygletStore.allocate()` legt Ressourcen als VertexList-Attribute über den
pyglet-Default-Shader an (`position` = vec3, `count = nbytes // 12`).
Ressourcen, deren Float-Anzahl nicht durch 3 teilbar ist
(camera_uniforms = 32, material_uniforms = 8, highlight_flags = n_verts),
würden ohne Padding abgeschnitten bzw. beim `update()` über die Kapazität
hinaus schreiben — der Default-Shader kennt nur vec3/vec4-Attribute, ein
eigener Multi-Attribut-Shader für die Production-`RenderMesh`-Ressourcen ist
dokumentierter Non-Goal (Gate 5, künftiges Entry-Point-Gate).

Bewusst NICHT Teil dieser Datei: das sichtbare Draw (eigene VBOs in
`playground/window.py`, analog `IntegrationLabWindow`). Dieser Store
speist ausschließlich die Production-`RenderMesh`-Buchhaltung
(GPU Resource Persistence, Counter, `resource_ids()`), nicht den
Bildschirm-Draw-Pfad des Fensters — identisch zur Lab-Rolle.
"""

from __future__ import annotations

from viewport.resource_store import PygletStore


class PlaygroundPygletStore(PygletStore):
    """Production-`PygletStore` mit vec3-ausgerichteter Allokation.

    Identisch zur Lab-Referenz `LabPygletStore` (siehe Moduldoc). Reine
    Harness-/Adapter-Maßnahme, keine Änderung an Production `viewport`.
    Benötigt einen aktiven GL-Kontext bei `allocate()` — darf erst NACH
    `pyglet.window.Window.__init__()` instanziiert/verwendet werden
    (siehe `playground/window.py::PlaygroundWindow._load_initial_scene`).
    """

    def allocate(self, name: str, nbytes: int) -> None:
        aligned = -(-nbytes // 12) * 12  # ceil auf Vielfache von 12 (vec3)
        super().allocate(name, aligned)
