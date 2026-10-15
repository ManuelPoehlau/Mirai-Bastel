"""Szenen speichern und laden im Production-Fenster (`PROVISIONAL`, Manu 2026-10-15).

Entscheidung: keine OS-Dateidialoge; Szenendateien liegen im Ordner `scenes/` (Repo-Wurzel,
in `.gitignore`) und erscheinen im temporären `SPACE`-Menü (`src/scene_menu.py`) als Zeilen:

    Szene speichern (Strg+S)    - die aktuelle Datei überschreiben, sonst eine neue anlegen
    Als neue Szene speichern    - immer eine neue Datei
    Datei: <name>               - die gespeicherten Szenen, neueste zuerst (höchstens 10)

`Strg+S` ist ein Vorschlag (INPUT_WIRING_MAP §10 „Save“), keine Artist-Input-Truth, und
liegt wie `SPACE` auf Fenster-Ebene (`install_handlers(..., save=...)`), nicht im BindingSet.

„Aktuelle Datei“ = die zuletzt geladene oder gespeicherte Szenendatei; wird ein Asset oder
`cube` geladen, gibt es keine mehr (`forget`), und `Strg+S` legt wieder eine neue an. Das
Schreiben und Laden selbst machen `Application.save_scene_file` bzw.
`Application.load_scene("file", scene_path=...)`; dieses Modul kennt nur Pfade und Labels und
importiert kein pyglet (headless testbar).
"""

from __future__ import annotations

import re
import time
from pathlib import Path

#: Endung der Szenendateien (Inhalt: `core.serialization`, JSON).
SCENE_SUFFIX = ".mirai.json"
#: Standardordner, relativ zur Repo-Wurzel (dieses Modul liegt in `src/`).
DEFAULT_SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes"
#: So viele Dateien zeigt das Menü höchstens (neueste zuerst), damit es ins Fenster passt.
MAX_LISTED_FILES = 10

SAVE_LABEL = "Szene speichern (Strg+S)"
SAVE_NEW_LABEL = "Als neue Szene speichern"
FILE_LABEL_PREFIX = "Datei: "


def is_scene_file(path: str | Path) -> bool:
    return str(path).lower().endswith(SCENE_SUFFIX)


def _stem(path: Path) -> str:
    return path.name[: -len(SCENE_SUFFIX)] if is_scene_file(path) else path.stem


class SceneFiles:
    """Pfade, Menü-Labels und die aktuelle Datei für eine `Application`."""

    def __init__(
        self,
        app,
        directory: str | Path = DEFAULT_SCENE_DIR,
        gl_types: dict | None = None,
        clock=time.localtime,
    ) -> None:
        self.app = app
        self.directory = Path(directory)
        self.gl_types = dict(gl_types or {})
        self.current: Path | None = None
        self._clock = clock
        # Label -> Datei der zuletzt gelisteten Einträge (`entries`).
        self._files_by_label: dict[str, Path] = {}

    # -- Liste / Menü -----------------------------------------------------------

    def files(self) -> list[Path]:
        """Die Szenendateien im Ordner, neueste zuerst (höchstens `MAX_LISTED_FILES`)."""
        if not self.directory.is_dir():
            return []
        found = [p for p in self.directory.iterdir() if p.is_file() and is_scene_file(p)]
        found.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
        return found[:MAX_LISTED_FILES]

    def entries(self) -> tuple[str, ...]:
        """Die Menü-Zeilen dieses Moduls (vor `cube` + Assets); liest den Ordner neu."""
        self._files_by_label = {FILE_LABEL_PREFIX + _stem(p): p for p in self.files()}
        return (SAVE_LABEL, SAVE_NEW_LABEL) + tuple(self._files_by_label)

    def handles(self, label: str) -> bool:
        return label in (SAVE_LABEL, SAVE_NEW_LABEL) or label in self._files_by_label

    def activate(self, label: str) -> bool:
        """Eine Menü-Zeile dieses Moduls ausführen. True = gespeichert bzw. geladen."""
        if label == SAVE_LABEL:
            return self.save() is not None
        if label == SAVE_NEW_LABEL:
            return self.save(new=True) is not None
        path = self._files_by_label.get(label)
        if path is None:
            return False
        return self.load(path)

    def refuse_add(self, label: str) -> bool:
        """Shift+Klick auf eine Zeile dieses Moduls: eine Szenendatei als Referenz
        hinzuzufügen gibt es (noch) nicht - Statuszeile, False."""
        self.app.set_status(f"{label!r}: only cube and the assets can be added as a Reference")
        return False

    # -- Speichern / Laden --------------------------------------------------------

    def new_path(self) -> Path:
        """Neuer Dateiname: `<Name des Edit-Objekts>_<Datum-Uhrzeit>`, bei Kollision `_2`..."""
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", self.app.scene.edit_object.name).strip("_")
        base = f"{name or 'scene'}_{time.strftime('%Y%m%d-%H%M%S', self._clock())}"
        path = self.directory / f"{base}{SCENE_SUFFIX}"
        counter = 2
        while path.exists():
            path = self.directory / f"{base}_{counter}{SCENE_SUFFIX}"
            counter += 1
        return path

    def save(self, new: bool = False) -> Path | None:
        """`Strg+S`: in die aktuelle Datei, sonst (oder mit `new`) in eine neue. Gibt den
        Pfad zurück, None = nicht gespeichert (Grund in der Statuszeile)."""
        path = self.current if (self.current is not None and not new) else self.new_path()
        try:
            saved = self.app.save_scene_file(path)
        except OSError as exc:
            self.app.set_status(f"Save scene failed: {exc}")
            return None
        if not saved:
            return None
        self.current = path
        return path

    def load(self, path: str | Path) -> bool:
        """Szenendatei laden; ein Fehler wird Statuszeile, die Szene bleibt dann unverändert."""
        path = Path(path)
        try:
            self.app.load_scene("file", scene_path=path, **self.gl_types)
        except Exception as exc:
            self.app.set_status(f"Scene file {path.name!r} failed: {exc}")
            return False
        self.current = path
        self.app.set_status(f"Scene: {path.name}")
        return True

    def forget(self) -> None:
        """Eine Nicht-Datei-Szene wurde geladen: `Strg+S` legt wieder eine neue Datei an."""
        self.current = None
