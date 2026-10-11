"""Temporärer Scene-Loader im Production-Fenster (PROVISIONAL).

`SPACE` öffnet am Cursor ein einfaches Kontextmenü mit den verfügbaren
Szenen; ein Klick auf eine Zeile lädt sie, ein Klick daneben, `SPACE` oder
`Esc` schließt. Der Wechsel selbst läuft über `Application.load_scene`
(Auswahl/History/Pick-Cache zurückgesetzt, Kamera neu ausgerichtet).

Bewusst Fenster-Ebene wie die Lab-Tasten (AD-013 H2, Variante G): keine
Neuerung im Binding-System — `SPACE` bleibt in `mirai.interaction.bindings`
unbelegt, und `install_handlers` bekommt das Menü nur auf Anforderung
(`menu=...`), der Symmetry Lab teilt die Verdrahtung also unverändert. Der
Key ist ein Engineering-Vorschlag, kein Artist-Input-Truth
(INPUT_WIRING_MAP.md §10 „Load“ = TBD). Das Modul ist temporär und darf mit
seiner Begründung wieder entfernt werden.

Einträge kommen aus der Asset-Registry (`examples/loaders/assets.py`,
AD-007) plus dem selbst gebauten `cube`: `("cube",) + asset_names()`.

Kein pyglet-Import auf Modulebene: Zeichnung und Textbreite bauen lazy
(Muster `playground/hud.py`), damit der Menüzustand headless testbar ist.
"""

from __future__ import annotations

from typing import Callable, Sequence

#: Layout in Fensterpixeln (y steigt nach oben, wie bei pyglet).
HEADER_HEIGHT = 24
ROW_HEIGHT = 22
PADDING = 8
#: Mindestbreite; die echte Breite folgt der breitesten Zeile.
MIN_WIDTH = 160

_FONT_SIZE_TITLE = 11
_FONT_SIZE_ROW = 12


def scene_entries() -> tuple[str, ...]:
    """Menü-Einträge in Reihenfolge: `cube` + die Registry-Assets.

    Braucht `examples/` auf `sys.path` (der Production-Entry-Point legt das
    in seinem Modulkopf an; Tests siehe `tests/test_application_obj_scene`)."""
    from loaders.assets import asset_names  # lazy — Muster scene_factory

    return ("cube",) + tuple(asset_names())


def load_named_scene(app, name: str, gl_types: dict | None = None) -> bool:
    """Szene per Menü-/Registry-Name laden (`Application.load_scene`).

    True = geladen; ein Fehlgriff wird als Statuszeile gemeldet statt als
    Traceback (derselbe Gedanke wie der CLI-Fallback in `main()`)."""
    try:
        if name == "cube":
            app.load_scene("cube", **(gl_types or {}))
        else:
            from loaders.assets import asset_path  # lazy — Muster scene_factory

            app.load_scene("obj", obj_path=asset_path(name), **(gl_types or {}))
    except Exception as exc:
        app.set_status(f"Scene {name!r} failed: {exc}")
        return False
    app.set_status(f"Scene: {name}")
    return True


class SceneMenu:
    """Das Kontextmenü: offener Zustand, Geometrie, Hover, Zeichnung.

    `load` bekommt den getroffenen Eintrags-Namen; `load_named_scene` fängt
    Ladefehler selbst ab, ein werfender Callback darf hier durchmarschieren
    (er ist dann ein Programmierfehler, kein Erwartungsfall)."""

    def __init__(self, entries: Sequence[str], load: Callable[[str], bool]) -> None:
        self.entries = tuple(entries)
        self._load = load
        self._open = False
        self._x = 0.0
        self._y = 0.0  # obere Kante
        self._width = MIN_WIDTH
        self._height = self._total_height()
        self._hover = -1
        # Lazy pyglet-Objekte (None = nicht gebaut bzw. pyglet nicht da).
        self._title = None
        self._labels: list | None = None
        self._background = None
        self._hover_rect = None

    # -- Zustand -------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def hover(self) -> int:
        """Index der gehoverten Zeile (-1 = keine)."""
        return self._hover

    @property
    def rect(self) -> tuple[float, float, int, int]:
        """Menü-Rechteck (x, obere Kante y, Breite, Höhe)."""
        return (self._x, self._y, self._width, self._height)

    def open(self, x: float, y: float, window_width: int, window_height: int) -> None:
        """Am Cursor öffnen, innerhalb des Fensters geklemmt (nicht genug Platz
        unten → klappt über dem Cursor auf)."""
        self._build_drawables()
        self._width = self._measure_width()
        self._height = self._total_height()
        self._x = min(max(0.0, float(x)), max(0.0, window_width - self._width))
        top = float(y)
        if top - self._height < 0:
            top = self._height
        self._y = min(top, float(window_height))
        self._place_drawables()
        self._hover = -1
        self._open = True

    def close(self) -> None:
        self._open = False
        self._hover = -1

    # -- Eingabe --------------------------------------------------------------

    def key(self, inp) -> bool:
        """Taste im offenen Menü: `SPACE`/`Esc` schließt (True = geschlossen).

        Alles andere ist beim Aufrufer modal zu schlucken — das Menü kennt
        keine weitere Aktion."""
        if (
            inp is not None
            and inp.kind == "key"
            and not inp.modifiers
            and inp.value in ("space", "ESCAPE")
        ):
            self.close()
            return True
        return False

    def motion(self, x: float, y: float) -> None:
        """Hover-Zeile aus der Cursorposition bestimmen (-1 = außerhalb)."""
        self._hover = self._row_at(x, y)
        self._update_hover_rect()

    def press(self, x: float, y: float) -> bool:
        """Klick verarbeiten: Treffer lädt die Zeile, außerhalb schließt das
        Menü. Immer modal — der Klick geht nie an die Application.
        True = eine Zeile wurde ausgelöst."""
        index = self._row_at(x, y)
        self.close()
        if index < 0:
            return False
        self._load(self.entries[index])
        return True

    # -- Zeichnung ------------------------------------------------------------

    def draw(self) -> None:
        """Das offene Menü über den Viewport zeichnen (Depth aus, Blend an —
        Muster `playground/window.py` HUD/Gizmo). Ohne gebaute pyglet-Objekte
        kein Menü; die App läuft dann einfach ohne sichtbares Menü weiter."""
        if not self._open:
            return
        if self._labels is None or self._background is None:
            return
        from pyglet import gl

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self._background.draw()
        if 0 <= self._hover < len(self.entries) and self._hover_rect is not None:
            self._hover_rect.draw()
        if self._title is not None:
            self._title.draw()
        for label in self._labels:
            label.draw()

    # -- Geometrie ------------------------------------------------------------

    def _total_height(self) -> int:
        return HEADER_HEIGHT + ROW_HEIGHT * len(self.entries)

    def _row_rect(self, index: int) -> tuple[float, float]:
        """Zeile `index` als (x, untere Kante) über die volle Menübreite."""
        top = self._y - HEADER_HEIGHT - index * ROW_HEIGHT
        return (self._x, top - ROW_HEIGHT)

    def _row_at(self, x: float, y: float) -> int:
        if not (self._x <= x <= self._x + self._width):
            return -1
        if not (self._y - self._height <= y <= self._y):
            return -1
        if y > self._y - HEADER_HEIGHT:
            return -1  # Kopfbereich trifft keine Zeile
        index = int((self._y - HEADER_HEIGHT - y) // ROW_HEIGHT)
        return index if 0 <= index < len(self.entries) else -1

    # -- Lazy pyglet ----------------------------------------------------------

    def _build_drawables(self) -> None:
        """Labels/Flächen anlegen (Textbreite wird danach messbar). Atomar und
        fehlertolerant: bringt es pyglet oder der GL-Kontext nicht, bleibt es
        bei der Zeichenschätzung in `_measure_width`."""
        if self._labels is not None:
            return
        try:
            from pyglet import shapes, text

            title = text.Label(
                "Szene laden (SPACE)",
                x=0,
                y=0,
                anchor_x="left",
                anchor_y="top",
                font_size=_FONT_SIZE_TITLE,
                color=(150, 160, 175, 255),
            )
            labels = [
                text.Label(
                    name,
                    x=0,
                    y=0,
                    anchor_x="left",
                    anchor_y="top",
                    font_size=_FONT_SIZE_ROW,
                    color=(230, 235, 245, 255),
                )
                for name in self.entries
            ]
            background = shapes.Rectangle(0, 0, 1, 1, color=(24, 26, 32, 240))
            hover_rect = shapes.Rectangle(0, 0, 1, 1, color=(64, 86, 128, 255))
            hover_rect.opacity = 0
        except Exception:
            return
        self._title = title
        self._labels = labels
        self._background = background
        self._hover_rect = hover_rect

    def _measure_width(self) -> int:
        if self._labels:
            widest = max(label.content_width for label in self._labels)
        else:
            # Headless-Schätzung (~9px/Zeichen), damit Zeile + Rand passen.
            widest = max((len(name) for name in self.entries), default=8) * 9
        return max(MIN_WIDTH, widest + 2 * PADDING + 6)

    def _place_drawables(self) -> None:
        if self._labels is None:
            return
        self._title.x = self._x + PADDING
        self._title.y = self._y - 6
        for index, label in enumerate(self._labels):
            label.x = self._x + PADDING
            label.y = self._y - HEADER_HEIGHT - index * ROW_HEIGHT - 5
        self._background.x = self._x
        self._background.y = self._y - self._height
        self._background.width = self._width
        self._background.height = self._height
        self._update_hover_rect()

    def _update_hover_rect(self) -> None:
        if self._hover_rect is None:
            return
        if 0 <= self._hover < len(self.entries):
            _, bottom = self._row_rect(self._hover)
            self._hover_rect.x = self._x + 2
            self._hover_rect.y = bottom + 1
            self._hover_rect.width = self._width - 4
            self._hover_rect.height = ROW_HEIGHT - 2
            self._hover_rect.opacity = 255
        else:
            self._hover_rect.opacity = 0
