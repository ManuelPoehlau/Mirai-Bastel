"""pyglet side of the Morph Lab on the app path.

The window handlers come from `src/main.py` (`install_handlers`, H6) and are not copied. The lab
passes `save=` (Ctrl+S writes the lab's scene file through `SceneFiles.save` →
`Application.save_scene_file`, AD-013 H7 note "Second user") but no SPACE menu: a runtime load
would build a new viewport without the lab's surface. It pushes two handlers on top, like
`experiments/subdivision_lab/lab_app_window.py`:

- `on_key_press`: `lab_app.lab_key_press`; every key that is not a lab key runs through the
  `on_key_press` of `main.py` with all its side effects (Shift/Ctrl tracking, Ctrl+S).
- `on_draw`: the draw of `main.py` (which draws the replacement surface through the viewport, H7),
  then the lab's HUD line.
"""

from __future__ import annotations

import time

from mirai.application import Application
from mirai.pyglet_input import key_from_pyglet

from .lab_app import MorphAppLab, hud_text, lab_key_press

HUD_MARGIN = 8
HUD_FONT_SIZE = 11
HUD_COLOR = (230, 230, 230, 255)
#: Smoothing of the HUD frame time (exponential moving average).
FRAME_EMA = 0.1


class HandlerRecorder:
    """Window stand-in for `install_handlers`: registers on the real window and remembers each
    handler by name; everything else is read live from the real window."""

    def __init__(self, window) -> None:
        self.window = window
        self.handlers: dict = {}

    def event(self, func):
        self.handlers[func.__name__] = func
        return self.window.event(func)

    def __getattr__(self, name: str):
        return getattr(self.window, name)


class LabHud:
    def __init__(self, lab: MorphAppLab, window, asset_name: str) -> None:
        self.lab = lab
        self.window = window
        self.asset_name = asset_name
        self.label = None
        self.frame_ms = None
        self._last = None

    def tick(self) -> None:
        now = time.perf_counter()
        if self._last is not None:
            ms = (now - self._last) * 1000.0
            self.frame_ms = ms if self.frame_ms is None else self.frame_ms + FRAME_EMA * (ms - self.frame_ms)
        self._last = now

    def text(self) -> str:
        return hud_text(self.lab, self.asset_name, self.frame_ms)

    def draw(self) -> None:
        import pyglet

        text = self.text()
        width = max(1, self.window.width - 2 * HUD_MARGIN)
        if self.label is None:
            self.label = pyglet.text.Label(
                text, x=HUD_MARGIN, y=self.window.height - HUD_MARGIN, width=width, multiline=True,
                anchor_y="top", font_size=HUD_FONT_SIZE, color=HUD_COLOR,
            )
        else:
            if self.label.width != width:
                self.label.width = width
            if self.label.y != self.window.height - HUD_MARGIN:
                self.label.y = self.window.height - HUD_MARGIN
            if self.label.text != text:
                self.label.text = text
        self.label.draw()


def install_lab_window(
    window, app: Application, lab: MorphAppLab, src_main, asset_name: str, save=None
) -> LabHud:
    """Installs the handlers of `src_main.install_handlers` (with `save=`) and the lab handlers
    above them."""
    import pyglet

    recorder = HandlerRecorder(window)
    src_main.install_handlers(recorder, app, save=save)
    main_key_press = recorder.handlers["on_key_press"]
    main_draw = recorder.handlers["on_draw"]
    hud = LabHud(lab, window, asset_name)

    def on_key_press(symbol: int, modifiers: int):
        inp = key_from_pyglet(symbol, modifiers)
        if inp is None:
            return main_key_press(symbol, modifiers)
        lab_key_press(app, lab, inp, forward=lambda _inp: main_key_press(symbol, modifiers))
        return pyglet.event.EVENT_HANDLED

    def on_draw():
        hud.tick()
        main_draw()
        hud.draw()
        # Otherwise the main.py draw underneath would run a second time.
        return pyglet.event.EVENT_HANDLED

    window.push_handlers(on_key_press=on_key_press, on_draw=on_draw)
    return hud
