# GUI-Framework-Spike: Dear ImGui (imgui-bundle) im Production-Fenster

Auftrag: [`docs/design/GUI_FRAMEWORK_SPIKE_BRIEF.md`](../../docs/design/GUI_FRAMEWORK_SPIKE_BRIEF.md). Ergebnis und Entscheidung:
[`AD-030`](../../docs/architecture/AD-030-GUI-FRAMEWORK.md). Status: Spike, `PROVISIONAL`, nichts davon liegt in `src/`;
`src/` ist unverändert.

```bash
pip install -r experiments/gui_framework_spike/requirements.txt
python experiments/gui_framework_spike/run.py [cube | Pfad.obj]      # echtes Production-Fenster + Outliner
xvfb-run -a python -m pytest experiments/gui_framework_spike/tests -q   # 18 Tests (9 ohne Display)
xvfb-run -a python experiments/gui_framework_spike/bench.py gollum_20k.obj --variant plain|open|closed|leaks
```

Der Outliner ist über den Knopf „Outliner [-]/[+]“ links oben umschaltbar (keine Taste: Manus Freigabe fehlt). Er zeigt die
Objekte mit Gruppen-Einrückung; Klick wählt (Shift = hinzufügen, Ctrl = entfernen, Alt = umschalten, wie im Viewport);
das Auge blendet über `HideObjects` aus. Aktionen sind nur in Modus `4` aktiv.

| Datei | Inhalt | Abhängigkeiten |
|---|---|---|
| `outliner_model.py` | Zeilen, Klick-Tabelle, Auge-Plan (reine Funktionen) | nur `core`, `mirai` |
| `input_gate.py` | Eingabe-Hoheit: wer bekommt welches Ereignis | keine |
| `imgui_layer.py` | Zeichnen, Event-Weitergabe, GL-Sicherung (lazy imgui/pyglet) | imgui-bundle, pyglet |
| `run.py` | komponiert `src/main.py` + Layer | wie `main.py` |
| `bench.py` | Frame-Zeit, Start, Speicher, GL-Lecks | wie `run.py` |
| `tests/` | Modell + Gate headless; Fenster-Integration unter xvfb | pytest |

Zum Umbenennen/Drag-Umsortieren/Rechtsklick: nur Rechtsklick-Popup und Textfeld (Filter) sind drin, um die Fähigkeit zu
zeigen; Umbenennen und Drag stehen nicht im Spike. Aufräumen bei „nein“: den Ordner löschen.
