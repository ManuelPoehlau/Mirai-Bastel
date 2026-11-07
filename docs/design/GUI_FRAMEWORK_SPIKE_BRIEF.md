# GUI-Framework-Spike — Auftrag für eine frische Session (2026-11-07)

**Status:** beauftragt von Manu („Machen wir so“). Größe L. Ergebnis ist ein AD mit *ja / nein / Bedingungen*, kein Umbau.

## Warum
Alles Panel-artige ist heute selbstgebaut auf pyglet (`src/hud.py` lesend, `src/scene_menu.py` SPACE-Menü). Es fehlen Klickzeilen,
Scroll-Listen, Bäume, Drag-and-Drop, Rechtsklick-Menüs und Texteingabe (Namen kommen aus `SET_NAMES`). Der Outliner braucht
genau das, und weitere Panels (Look, Regions, Rig) folgen. Keine Notlösung bauen: erst das Framework klären.

## Stand, auf dem die Session aufsetzt (nichts davon ändern)
- Outliner-**Daten und Commands stehen** (AD-021 §6.8, `tests/test_object_outliner.py`): Gruppen (`ObjectState.GROUP`, `parent`),
  `hidden`, `HideObjects`/`IsolateObjects`/`ShowAllObjects`/`DuplicateObjects`/`GroupObjects`/`UngroupObjects`/`SelectObjectGroup`
  über `app.dispatch_command` bzw. `ObjectController.management_command`. Tasten (Modus `4`): Ctrl+H, Ctrl+Shift+H, Alt+H,
  Ctrl+G, Alt+G, Ctrl+Alt+G. Duplizieren: keine Taste, kommt als Panel-Aktion (Rechtsklick/Button).
- Eingabe-Regel: das aktive `BindingSet` ist die einzige Eingabe-Wahrheit (AD-013 Addendum 2026-10-28); `config/keymap.json` ist
  Manus Entscheidungsschicht — keine Taste ohne seine Freigabe.
- Datenfluss: Core → Viewport, nie zurück. Ein Panel liest Zustand und schickt Commands, es hält keinen Dokumentzustand.
- Lesen vor dem Start: `docs/design/GUI_Bestandsaufnahme.md`, `GUI_STAGE1_HUD.md`, `UX_RESEARCH.md`, `src/hud.py`, `src/main.py`
  (Fenster, `install_handlers`), AD-021 §6.8.

## Kandidat und Alternativen
- **Dear ImGui** über `imgui-bundle` (oder `pyimgui`) mit pyglet-Backend — Kandidat 1 (Empfehlung von Manu/ChatGPT).
- Qt/PySide6 — nur zum Vergleichen: eigener Event-Loop neben pyglet, voraussichtlich zu groß.
- Weiter selbst bauen — nur als Vergleichsbasis (Aufwand für Texteingabe, Scrollen, Drag-and-Drop schätzen, nicht bauen).

## Der Spike
Ein **Outliner-Panel im echten Production-Fenster** (`src/main.py`), umschaltbar, im Minimalumfang:
Liste der Objekte mit Einrückung nach Gruppen, Klick = Auswahl (Shift/Ctrl wie im Viewport), Auge = Hide/Show.
Bewusst nicht im Spike: Drag-Umsortieren, Umbenennen, Rechtsklick (nur prüfen, dass das Framework sie kann).
Das Panel ist der erste echte Anwendungsfall und soll bei „ja“ bleiben, nicht weggeworfen werden.

## Zu messen / zu klären (Antworten ins AD)
1. **Eingabe-Hoheit:** ImGui bekommt Maus/Tasten nur über einem Panel oder bei aktivem Textfeld (`want_capture_mouse/keyboard`);
   sonst geht alles unverändert an `Application` (BindingSet). Orbit, Pick, Lasso, Gesten dürfen sich nicht ändern.
   Testfälle: Klick im Panel wählt kein Viewport-Objekt; Taste im Textfeld löst keinen Command aus; Cursor-Wrap bei W/E/R.
2. **GL:** gleicher Kontext wie `GLRenderStore`/Overlays; Shader-Version, Zustandslecks (Depth, Blend, Scissor, VAO) in beide
   Richtungen; Funktion unter `xvfb-run` und in der Cloud-Umgebung; Verhalten ohne GL (die Tests dürfen nicht brechen:
   Import lazy, wie bei `hud.py`/`scene_menu.py`).
3. **Kosten:** Frame-Zeit mit/ohne Panel (Leerlauf und Orbit auf dem schweren Testmesh), Speicher, Startzeit.
4. **Abhängigkeit:** Python 3.9+, Wheels für Windows/Linux/macOS, Größe, Lizenz, Pflegezustand; Pinning in `requirements*.txt`.
5. **Artist-Frage (für Manu):** Optik, Skalierung/HiDPI, Schrift, Farben passend zur HUD; Screenshot im echten Fenster vorlegen.
6. **Migration:** was von `hud.py` und dem SPACE-Menü später umzieht und was bleibt (nicht umsetzen, nur einordnen).
7. **Testbarkeit:** Panel-Logik (welche Zeilen, welcher Command bei welchem Klick) pyglet- und imgui-frei als reine Funktionen
   halten, damit sie headless getestet wird — nur das Zeichnen hängt am Framework.

## Abbruch / Ergebnis
- Scheitert eines der Muss-Kriterien (1: Eingabe-Hoheit, 2: GL-Stabilität, 4: Installierbarkeit), zurück zu Manu mit Befund und
  der nächstbesten Alternative; kein „irgendwie hinbiegen“.
- Ergebnis: `docs/architecture/AD-0xx-GUI-FRAMEWORK.md` mit Entscheidung, Bedingungen, Messwerten und Migrationsplan; dazu der
  lauffähige Spike auf einem eigenen Branch. Kein Merge nach `src/` ohne Manus Entscheidung (CLAUDE.md: nichts aus
  `experiments/` ohne dokumentierte Freigabe nach `src/`).
