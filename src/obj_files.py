"""OBJ-Import/-Export im SPACE-Menü (`PROVISIONAL`, wie `src/scene_files.py`: keine OS-Dateidialoge).

Der Ordner `obj/` (Repo-Wurzel, in `.gitignore`) ist Quelle und Ziel; im `SPACE`-Menü erscheinen:

    OBJ exportieren              - das Edit-Objekt (Weltraum) als neue Datei `<Name>_<Datum-Uhrzeit>.obj`
    OBJ importieren: <name>      - die `.obj`-Dateien des Ordners, neueste zuerst (höchstens 10);
                                   ein Klick fügt sie als neues, bearbeitbares Objekt hinzu

Schreiben und Einlesen machen `Application.export_obj` / `Application.import_obj`; dieses Modul
kennt nur Pfade und Labels und importiert kein pyglet (headless testbar).
"""

from __future__ import annotations

import re
import time
from pathlib import Path

DEFAULT_OBJ_DIR = Path(__file__).resolve().parent.parent / "obj"
MAX_LISTED_FILES = 10

EXPORT_LABEL = "OBJ exportieren"
IMPORT_LABEL_PREFIX = "OBJ importieren: "


class ObjFiles:
    def __init__(self, app, directory: str | Path = DEFAULT_OBJ_DIR, clock=time.localtime) -> None:
        self.app = app
        self.directory = Path(directory)
        self._clock = clock
        self._files_by_label: dict[str, Path] = {}

    def files(self) -> list[Path]:
        if not self.directory.is_dir():
            return []
        found = [p for p in self.directory.iterdir() if p.is_file() and p.suffix.lower() == ".obj"]
        found.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
        return found[:MAX_LISTED_FILES]

    def entries(self) -> tuple[str, ...]:
        self._files_by_label = {IMPORT_LABEL_PREFIX + p.stem: p for p in self.files()}
        return (EXPORT_LABEL,) + tuple(self._files_by_label)

    def handles(self, label: str) -> bool:
        return label == EXPORT_LABEL or label in self._files_by_label

    def activate(self, label: str) -> bool:
        if label == EXPORT_LABEL:
            return self.export()
        path = self._files_by_label.get(label)
        return path is not None and self.import_file(path)

    def refuse_add(self, label: str) -> bool:
        self.app.set_status(f"{label!r}: OBJ files cannot be added as a Reference")
        return False

    def new_path(self) -> Path:
        name = re.sub(r"[^A-Za-z0-9_-]+", "_", self.app.scene.edit_object.name).strip("_")
        base = f"{name or 'object'}_{time.strftime('%Y%m%d-%H%M%S', self._clock())}"
        path = self.directory / f"{base}.obj"
        counter = 2
        while path.exists():
            path = self.directory / f"{base}_{counter}.obj"
            counter += 1
        return path

    def export(self) -> bool:
        try:
            return self.app.export_obj(self.new_path())
        except OSError as exc:
            self.app.set_status(f"Export OBJ failed: {exc}")
            return False

    def import_file(self, path: str | Path) -> bool:
        path = Path(path)
        try:
            return self.app.import_obj(path) is not None
        except Exception as exc:
            self.app.set_status(f"Import OBJ {path.name!r} failed: {exc}")
            return False
