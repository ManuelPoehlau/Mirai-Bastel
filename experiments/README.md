# Experiments

Kleine technische Experimente und Praxistests. Experimente dürfen bewusst
isoliert, minimal und nicht production-ready sein.

Sie dienen dazu, technische Fragen und Bedienideen praktisch zu prüfen,
bevor daraus Produktionscode unter `src/` wird.

## Aktuelle Experimente

### `mirai_bastel_core_V1/`

Abgeschlossener Core-V1-Milestone. Enthält den vollständigen Referenzstand
des damaligen Core-Experiments einschließlich Tests und Review-Dokumentation.

### `mirai_bastel_viewport_V1/`

Abgeschlossener interaktiver Praxistest für die Verbindung des Core mit einem
minimalen OpenGL-Viewport. Der Test bestätigt insbesondere Scene/Mesh,
Selection, Move, Commit, History/Undo/Redo sowie grundlegende Kamera-
Interaktion.

Der Viewport-V1-Code ist **kein Produktions-Viewport**. Er bleibt als
Referenz- und Teststand vollständig unter `experiments/`, während die
endgültige `src/`-Struktur separat entwickelt wird.
