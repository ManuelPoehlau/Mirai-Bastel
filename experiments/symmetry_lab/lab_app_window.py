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
- `on_draw`: erst der Draw aus `main.py`, dann die Lab-HUD-Zeile.

Um den `main.py`-Handler aufrufen zu können, bekommt `install_handlers` einen
dünnen Stellvertreter des Fensters, der jeden `@window.event`-Handler am echten
Fenster registriert und sich zusätzlich merkt — öffentliche pyglet-API, kein
Zugriff auf pyglets Handler-Stack.
"""

from __future__ import annotations

from mirai.application import Application
from mirai.pyglet_input import key_from_pyglet

from .lab_app import SymmetryAppLab, hud_text, lab_key_press

HUD_MARGIN = 8
HUD_FONT_SIZE = 11
HUD_COLOR = (230, 230, 230, 255)


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
    """Eine Textzeile unten links: Symmetrie-Zustand + `app.status_message`."""

    def __init__(self, app: Application, window) -> None:
        self.app = app
        self.window = window
        self.label = None

    def text(self) -> str:
        return hud_text(self.app)

    def draw(self) -> None:
        import pyglet

        text = self.text()
        if self.label is None:
            self.label = pyglet.text.Label(
                text,
                x=HUD_MARGIN,
                y=HUD_MARGIN,
                font_size=HUD_FONT_SIZE,
                color=HUD_COLOR,
            )
        elif self.label.text != text:
            self.label.text = text
        self.label.draw()


def install_lab_window(window, app: Application, lab: SymmetryAppLab, src_main) -> LabHud:
    """Installiert die Handler aus `src_main.install_handlers` und darüber die
    Lab-Handler. `src_main` = das Modul `src/main.py`."""
    import pyglet

    recorder = HandlerRecorder(window)
    src_main.install_handlers(recorder, app)
    main_key_press = recorder.handlers["on_key_press"]
    main_draw = recorder.handlers["on_draw"]
    hud = LabHud(app, window)

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
