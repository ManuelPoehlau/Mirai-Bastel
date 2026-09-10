"""Mirai-Bastel — Integration Lab / Test Studio.

Ein Integration Harness / Test Studio — KEIN neuer Production-Viewport und
KEIN neuer Modeler.

Das Lab verbindet erstmals mehrere unabhängig entwickelte, teilweise
validierte Bausteine in einer gemeinsamen praktischen Testumgebung:

    src/core                        Domain-Wahrheit (Scene / Mesh)
    OBJ Loader (Rigging-Experiment) OBJ -> ObjMeshData (unverändert, headless)
    Viewport V0.2                   Render-/Performance-Schicht (unverändert)

Das Lab selbst ist additiv und isoliert: Es legt ausschließlich Adapter/
Wrapper/Bindings an und verändert weder `src/core` noch bestehende
Experimente. Die zentrale Domain-Wahrheit bleibt `src/core`; die V0.2-Render-
Darstellung ist davon abgeleitet (Core Mesh = Wahrheit, V0.2 Render Mesh =
abgeleitete Darstellung).

Siehe README.md im Lab-Ordner für Zweck, Architektur, Status und Grenzen.
"""