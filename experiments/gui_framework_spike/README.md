# GUI-Framework: Messskript

Der Spike (Dear ImGui / `imgui-bundle` im Production-Fenster) ist seit 2026-11-07 nach `src/gui/` übernommen, siehe
[AD-030](../../docs/architecture/AD-030-GUI-FRAMEWORK.md) §9. Hier bleibt nur das Messwerkzeug:

```bash
# je Variante ein eigener Prozess; ohne xvfb auf dem Referenz-PC mit echter GPU
python experiments/gui_framework_spike/bench.py gollum_20k.obj --variant plain|open|closed
python experiments/gui_framework_spike/bench.py --variant leaks      # GL-Zustand in beide Richtungen
```

`screenshot_outliner.png`: der Outliner im echten Fenster (Stand des Spikes, für die Artist-Abnahme).
