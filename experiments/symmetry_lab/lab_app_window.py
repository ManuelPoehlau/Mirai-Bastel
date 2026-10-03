"""pyglet-Anbindung des Labs auf dem App-Pfad (WP-SYM-LAB-03 Slice 1b).

Die Fenster-Handler kommen aus `src/main.py` (`install_handlers`, Hook H6) und
werden nicht kopiert. Das Lab legt nur zwei Handler darüber
(`window.push_handlers`):

- `on_key_press`: die Lab-Entscheidung (`lab_app.lab_key_press`). Jede Taste,
  die nicht zum Lab gehört, läuft durch den `on_key_press` aus `main.py` — mit
  allen seinen Seiteneffekten (Shift-Tracking für den Knife-Hover, WP-KNIFE-01
  UX2b; `app.key_press`). Eine Lab-Taste (S, M, B mit Modifiern) erreicht ihn
  nicht; sein Shift-Tracking reagiert nur auf die Shift-Symbole selbst
  (`shift_keys_after` gibt sonst `None`), die nie Lab-Tasten sind — es geht also
  nichts verloren. Immer `EVENT_HANDLED`, wie `main.py` (Esc schließt das
  Fenster nicht, H2-R3).
- `on_draw`: erst der Draw aus `main.py`, dann die Lab-HUD-Zeile (Slice 2: volle
  Zeile wie die alte Statuszeile, `lab_app.hud_text`) und darüber, solange die
  Re-Symmetrize-Vorschau offen ist, die blaue Vorschau-Zeile (Slice 3,
  `lab_app.preview_text`, Farbe wie im alten `lab_window`).

Um den `main.py`-Handler aufrufen zu können, bekommt `install_handlers` einen
dünnen Stellvertreter des Fensters, der jeden `@window.event`-Handler am echten
Fenster registriert und sich zusätzlich merkt — öffentliche pyglet-API, kein
Zugriff auf pyglets Handler-Stack.
"""

from __future__ import annotations

from mirai.application import Application
from mirai.pyglet_input import key_from_pyglet

from .lab_app import SymmetryAppLab, hud_text, lab_key_press, preview_text

HUD_MARGIN = 8
HUD_FONT_SIZE = 11
HUD_COLOR = (230, 230, 230, 255)
#: Vorschau-Zeile, Farbe aus dem alten `lab_window` (README-Legende: „blaue Textzeile").
PREVIEW_COLOR = (130, 170, 255, 255)
PREVIEW_GAP = 6


class HandlerRecorder:
    """Fenster-Stellvertreter für `install_handlers`: registriert am echten
    Fenster und merkt sich jeden Handler unter seinem Namen; alles andere
    (`width`, `height`, `clear`, …) liest er live vom echten Fenster."""

    def __init__(self, window) -> None:
        self.window = window
        self.handlers: dict = {}

    def event(self, func):
        self.handlers[func.__name__] = func
        return self.window.event(func)

    def __getattr__(self, name: str):
        return getattr(self.window, name)


class LabHud:
    """Die Lab-Zeile unten links (`lab_app.hud_text`); bricht an der Fensterbreite
    um wie die alte Statuszeile (Slice 7), damit die Statusmeldung am Ende nicht
    abgeschnitten wird. Darüber die Vorschau-Zeile (Slice 3), nur bei offener
    Vorschau."""

    def __init__(self, app: Application, lab: SymmetryAppLab, window, asset_name: str) -> None:
        self.app = app
        self.lab = lab
        self.window = window
        self.asset_name = asset_name
        self.label = None
        self.preview_label = None

    def text(self) -> str:
        return hud_text(self.app, self.asset_name, self.lab.report)

    def preview_text(self) -> str:
        return preview_text(self.lab)

    def draw(self) -> None:
        import pyglet

        text = self.text()
        width = max(1, self.window.width - 2 * HUD_MARGIN)
        if self.label is None:
            self.label = pyglet.text.Label(
                text,
                x=HUD_MARGIN,
                y=HUD_MARGIN,
                width=width,
                multiline=True,
                anchor_y="bottom",
                font_size=HUD_FONT_SIZE,
                color=HUD_COLOR,
            )
        else:
            if self.label.width != width:
                self.label.width = width
            if self.label.text != text:
                self.label.text = text
        self.label.draw()

        preview = self.preview_text()
        if not preview:
            return
        y = HUD_MARGIN + self.label.content_height + PREVIEW_GAP
        if self.preview_label is None:
            self.preview_label = pyglet.text.Label(
                preview,
                x=HUD_MARGIN,
                y=y,
                width=width,
                multiline=True,
                anchor_y="bottom",
                font_size=HUD_FONT_SIZE,
                color=PREVIEW_COLOR,
            )
        else:
            if self.preview_label.width != width:
                self.preview_label.width = width
            if self.preview_label.text != preview:
                self.preview_label.text = preview
            if self.preview_label.y != y:
                self.preview_label.y = y
        self.preview_label.draw()


def install_lab_window(
    window, app: Application, lab: SymmetryAppLab, src_main, asset_name: str
) -> LabHud:
    """Installiert die Handler aus `src_main.install_handlers` und darüber die
    Lab-Handler. `src_main` = das Modul `src/main.py`."""
    import pyglet

    recorder = HandlerRecorder(window)
    src_main.install_handlers(recorder, app)
    main_key_press = recorder.handlers["on_key_press"]
    main_draw = recorder.handlers["on_draw"]
    hud = LabHud(app, lab, window, asset_name)

    def on_key_press(symbol: int, modifiers: int):
        inp = key_from_pyglet(symbol, modifiers)
        if inp is None:
            return main_key_press(symbol, modifiers)
        lab_key_press(app, lab, inp, forward=lambda _inp: main_key_press(symbol, modifiers))
        return pyglet.event.EVENT_HANDLED

    def on_draw():
        main_draw()
        hud.draw()
        # Sonst liefe der darunterliegende main.py-Draw ein zweites Mal.
        return pyglet.event.EVENT_HANDLED

    window.push_handlers(on_key_press=on_key_press, on_draw=on_draw)
    return hud
