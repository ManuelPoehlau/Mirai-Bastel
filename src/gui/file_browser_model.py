"""Datei-Browser (Explorer-Ansicht) - reine Logik, ohne imgui, pyglet und Application (Manu 2026-11-18, `PROVISIONAL`).

Öffnen, Importieren und Bild-Laden (Textur, Iris, Lederhaut) brauchen mehr als „die letzten 10 Dateien eines festen
Ordners“ oder einen getippten Pfad: der Artist durchsucht das ganze System wie im Windows-Explorer. Dieses Modul hält
den Zustand dieser Ansicht; `gui.file_browser` zeichnet sie.

    Ordner:    `go` / `up` / `back` / `forward` / `refresh`; über dem Laufwerksstamm (Windows) steht die Liste der
               Laufwerke (`directory is None`)
    Liste:     Ordner zuerst, dann Dateien; nur Dateien, die der Dateityp-Filter durchlässt; ein Suchtext (Teil des
               Namens) wirkt auf beide; Sortierung nach Name (natürlich: `a2` vor `a10`), Datum oder Größe
    Pfadfeld:  `submit` nimmt einen getippten Pfad (Ordner: hinein, Datei: wählen; Anführungszeichen, `~` und relative
               Pfade sind erlaubt) - der alte Weg bleibt also möglich
    Orte:      Home, Desktop, Dokumente, Downloads, Bilder, die Laufwerke und die Ordner, die der Aufrufer nennt
    Gedächtnis: `LastDirs` merkt je Zweck (`scene`, `mesh`, `image`) den zuletzt benutzten Ordner und schreibt ihn auf
               Wunsch in eine kleine JSON-Datei, damit der nächste Import dort beginnt, wo der letzte endete

Nichts hier verändert eine Datei; ein Fehler (kein Zugriff, Ordner weg) steht in `error`, der Browser bleibt im alten Ordner.
"""

from __future__ import annotations

import json
import os
import re
import string
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

SORT_KEYS = ("name", "date", "size")


# -- Dateityp-Filter ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class FileFilter:
    """Ein Eintrag der Dateityp-Auswahl; `suffixes` kleingeschrieben mit Punkt (`.mirai.json` zählt als eine Endung);
    leer = jede Datei."""

    label: str
    suffixes: tuple[str, ...] = ()

    def matches(self, name: str) -> bool:
        low = name.lower()
        return not self.suffixes or any(low.endswith(s) for s in self.suffixes)


SCENE_FILTER = FileFilter("Szenen (*.mirai.json)", (".mirai.json",))
OBJ_FILTER = FileFilter("OBJ-Meshes (*.obj)", (".obj",))
IMAGE_FILTER = FileFilter("Bilder (png, jpg, bmp, tga, tif)", (".png", ".jpg", ".jpeg", ".bmp", ".tga", ".tif", ".tiff"))
ALL_FILTER = FileFilter("Alle Dateien (*.*)")


# -- Einträge ---------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    name: str
    path: Path
    is_dir: bool
    size: int = 0
    mtime: float = 0.0
    hidden: bool = False
    drive: bool = False  # die Laufwerksliste: der Name ist der Stamm („C:\“)


@dataclass(frozen=True)
class Place:
    label: str
    path: Path


def natural_key(name: str) -> list:
    """`a2` vor `a10`, Groß-/Kleinschreibung egal."""
    return [int(p) if p.isdigit() else p.casefold() for p in re.split(r"(\d+)", name)]


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if value < 1024.0 or unit == "TB":
            return f"{value:.1f} {unit}" if value < 100 else f"{value:.0f} {unit}"
    return f"{size} B"  # unerreichbar


def format_time(mtime: float) -> str:
    try:
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(mtime))
    except (OverflowError, OSError, ValueError):
        return ""


def clean_typed_path(text: str) -> str:
    return text.strip().strip('"').strip()


def _is_hidden(entry: os.DirEntry) -> bool:
    if entry.name.startswith("."):
        return True
    try:
        attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & 0x2 or attrs & 0x4)  # FILE_ATTRIBUTE_HIDDEN | _SYSTEM (nur Windows setzt es)


def list_drives() -> list[Path]:
    """Die Laufwerksstämme (Windows: `GetLogicalDrives`, ohne ein Laufwerk anzufassen; sonst `/`)."""
    if os.name != "nt":
        return [Path("/")]
    try:
        import ctypes

        mask = ctypes.windll.kernel32.GetLogicalDrives()  # type: ignore[attr-defined]
    except Exception:  # kein ctypes.windll: die Buchstaben der Reihe nach
        return [Path(f"{c}:\\") for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]
    return [Path(f"{c}:\\") for i, c in enumerate(string.ascii_uppercase) if mask & (1 << i)]


def default_places(home: Path | None = None, extra: Iterable[tuple[str, Path]] = ()) -> list[Place]:
    """Die Orte links: Home, die üblichen Benutzerordner (die es gibt) und die Ordner des Aufrufers; Laufwerke kommen
    getrennt (`list_drives`), weil sich ihre Liste ändern kann."""
    home = Path.home() if home is None else home
    found: list[Place] = [Place("Home", home)]
    for label, name in (("Desktop", "Desktop"), ("Dokumente", "Documents"), ("Downloads", "Downloads"),
                        ("Bilder", "Pictures")):
        path = home / name
        if path.is_dir():
            found.append(Place(label, path))
    for label, path in extra:
        if Path(path).is_dir():
            found.append(Place(label, Path(path)))
    return found


# -- Gedächtnis -------------------------------------------------------------------------------------------------------


class LastDirs:
    """Je Zweck der zuletzt benutzte Ordner. Mit `store` (JSON-Datei) bleibt er über Sitzungen erhalten; ein
    kaputter oder fehlender Speicher ist kein Fehler (dann beginnt der Browser im Standardordner)."""

    def __init__(self, store: str | Path | None = None) -> None:
        self.store = None if store is None else Path(store)
        self._dirs: dict[str, str] = {}
        if self.store is not None:
            try:
                data = json.loads(self.store.read_text(encoding="utf-8"))
                self._dirs = {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
            except (OSError, ValueError):
                pass

    def get(self, purpose: str, default: Path | None = None) -> Path | None:
        """Der gemerkte Ordner, falls es ihn noch gibt, sonst `default` (falls es ihn gibt), sonst None."""
        for text in (self._dirs.get(purpose), None if default is None else str(default)):
            if text and Path(text).is_dir():
                return Path(text)
        return None

    def remember(self, purpose: str, directory: str | Path) -> None:
        self._dirs[purpose] = str(directory)
        if self.store is None:
            return
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            self.store.write_text(json.dumps(self._dirs, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # ein Gedächtnis, das nicht schreibt, hält den Import nicht auf


class RecentFiles:
    """„Zuletzt geöffnete Dateien“ (Datei-Menü): die letzten `limit` geöffneten Szenen und importierten Meshes, neueste
    zuerst, je Pfad einmal. Mit `store` bleibt die Liste über Sitzungen erhalten; was es nicht mehr gibt, wird nicht
    angeboten (bleibt aber im Speicher, falls ein Laufwerk nur gerade fehlt)."""

    LIMIT = 10

    def __init__(self, store: str | Path | None = None, limit: int = LIMIT) -> None:
        self.store = None if store is None else Path(store)
        self.limit = limit
        self._items: list[tuple[str, str]] = []
        if self.store is not None:
            try:
                data = json.loads(self.store.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._items = [(str(k), str(p)) for k, p in data if isinstance(k, str) and isinstance(p, str)]
            except (OSError, ValueError, TypeError):
                pass

    def add(self, kind: str, path: str | Path) -> None:
        text = str(Path(os.path.abspath(str(path))))
        self._items = [(kind, text)] + [i for i in self._items if i[1] != text]
        del self._items[self.limit * 3:]  # Reserve für Einträge, die gerade nicht erreichbar sind
        if self.store is None:
            return
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            self.store.write_text(json.dumps(self._items, indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def items(self) -> list[tuple[str, Path]]:
        """(Art, Pfad) der vorhandenen Dateien, höchstens `limit`."""
        found = [(kind, Path(p)) for kind, p in self._items if Path(p).is_file()]
        return found[: self.limit]


# -- Das Modell -------------------------------------------------------------------------------------------------------


@dataclass
class BrowserModel:
    """Der Zustand einer Browser-Sitzung. `directory is None`: die Laufwerksliste."""

    filters: tuple[FileFilter, ...] = (ALL_FILTER,)
    start: Path | None = None
    places: list[Place] = field(default_factory=list)
    drives: Callable[[], list[Path]] = list_drives

    def __post_init__(self) -> None:
        self.directory: Path | None = None
        self.query = ""
        self.filter_index = 0
        self.show_hidden = False
        self.sort_key = "name"
        self.sort_descending = False
        self.error = ""
        self.selected: Path | None = None
        self._all: list[Entry] = []
        self._back: list[Path | None] = []
        self._forward: list[Path | None] = []
        target = self.start if self.start is not None and Path(self.start).is_dir() else Path.home()
        if not self.go(target, remember=False):
            self.go(None, remember=False)

    # -- Ordnerwechsel -----------------------------------------------------------------------------------------------
    @property
    def filter(self) -> FileFilter:
        return self.filters[min(self.filter_index, len(self.filters) - 1)]

    def go(self, target: str | Path | None, remember: bool = True) -> bool:
        """In einen Ordner (None: die Laufwerksliste). False = nicht möglich, `error` nennt den Grund; der Ordner
        bleibt dann, wo er war."""
        before = self.directory
        if target is None:
            entries = [Entry(str(d), d, True, drive=True) for d in self.drives()]
            path = None
        else:
            path = Path(os.path.normpath(os.path.abspath(str(target))))
            try:
                entries = self._scan(path)
            except FileNotFoundError:
                self.error = f"{path} nicht gefunden"
                return False
            except NotADirectoryError:
                self.error = f"{path} ist kein Ordner"
                return False
            except PermissionError:
                self.error = f"Kein Zugriff auf {path}"
                return False
            except OSError as exc:
                self.error = f"{path}: {exc.strerror or exc}"
                return False
        if remember and path != before:
            self._back.append(before)
            self._forward.clear()
        self.directory, self._all, self.error = path, entries, ""
        self.selected = None
        return True

    def _scan(self, path: Path) -> list[Entry]:
        found: list[Entry] = []
        with os.scandir(path) as it:
            for entry in it:
                try:
                    is_dir = entry.is_dir()
                    info = entry.stat()
                except OSError:
                    continue  # ein Eintrag, den das System nicht herausgibt (kaputter Link, gesperrt): überspringen
                found.append(Entry(entry.name, Path(entry.path), is_dir, 0 if is_dir else info.st_size, info.st_mtime,
                                   hidden=_is_hidden(entry)))
        return found

    def refresh(self) -> bool:
        keep = self.selected
        ok = self.go(self.directory, remember=False)
        if ok:
            self.selected = keep if keep is not None and any(e.path == keep for e in self._all) else None
        return ok

    def up(self) -> bool:
        if self.directory is None:
            return False
        parent = self.directory.parent
        if parent == self.directory:  # Stamm: Windows zeigt dann die Laufwerke, sonst bleibt es
            return self.go(None) if os.name == "nt" else False
        return self.go(parent)

    def can_up(self) -> bool:
        return self.directory is not None and (self.directory.parent != self.directory or os.name == "nt")

    def back(self) -> bool:
        if not self._back:
            return False
        target = self._back.pop()
        here = self.directory
        if not self.go(target, remember=False):
            self._back.append(target)
            return False
        self._forward.append(here)
        return True

    def forward(self) -> bool:
        if not self._forward:
            return False
        target = self._forward.pop()
        here = self.directory
        if not self.go(target, remember=False):
            self._forward.append(target)
            return False
        self._back.append(here)
        return True

    def can_back(self) -> bool:
        return bool(self._back)

    def can_forward(self) -> bool:
        return bool(self._forward)

    def breadcrumbs(self) -> list[tuple[str, Path | None]]:
        """Der Pfad als anklickbare Teile, vorn „Dieser PC“ (Laufwerksliste, nur Windows)."""
        crumbs: list[tuple[str, Path | None]] = [("Dieser PC", None)] if os.name == "nt" else []
        if self.directory is None:
            return crumbs or [("/", Path("/"))]
        parts: list[tuple[str, Path | None]] = []
        node = self.directory
        while True:
            parts.append((node.name or str(node), node))
            if node.parent == node:
                break
            node = node.parent
        return crumbs + parts[::-1]

    # -- Liste -------------------------------------------------------------------------------------------------------
    def set_sort(self, key: str, descending: bool | None = None) -> None:
        """Ein Klick auf dieselbe Spalte kehrt die Richtung um (`descending=None`); eine neue Spalte beginnt
        aufsteigend, das Datum mit dem Neuesten oben."""
        if key not in SORT_KEYS:
            raise ValueError(key)
        if descending is None:
            descending = (not self.sort_descending) if key == self.sort_key else key == "date"
        self.sort_key, self.sort_descending = key, descending

    def visible(self) -> list[Entry]:
        """Was die Liste zeigt: Ordner zuerst, dann Dateien (nur die des Dateityps), je nach Suchtext und Sortierung."""
        if self.directory is None:
            return list(self._all)
        query = self.query.strip().casefold()
        rows = []
        for e in self._all:
            if e.hidden and not self.show_hidden:
                continue
            if not e.is_dir and not self.filter.matches(e.name):
                continue
            if query and query not in e.name.casefold():
                continue
            rows.append(e)
        if self.sort_key == "date":
            rows.sort(key=lambda e: (e.mtime, natural_key(e.name)), reverse=self.sort_descending)
        elif self.sort_key == "size":
            rows.sort(key=lambda e: (e.size, natural_key(e.name)), reverse=self.sort_descending)
        else:
            rows.sort(key=lambda e: natural_key(e.name), reverse=self.sort_descending)
        return [e for e in rows if e.is_dir] + [e for e in rows if not e.is_dir]

    # -- Auswahl -----------------------------------------------------------------------------------------------------
    def select(self, entry: Entry) -> None:
        self.selected = None if entry.is_dir else entry.path

    def activate(self, entry: Entry) -> Path | None:
        """Doppelklick: ein Ordner öffnet sich (None), eine Datei ist die Wahl."""
        if entry.is_dir:
            self.go(entry.path)
            return None
        self.selected = entry.path
        return entry.path

    def submit(self, text: str) -> Path | None:
        """Ein getippter Pfad oder Dateiname (Pfadfeld, Namensfeld, Enter): ein Ordner wird geöffnet (None), eine
        vorhandene Datei ist die Wahl. Sonst bleibt `error` und es kommt None."""
        typed = clean_typed_path(text)
        if not typed:
            return None
        if os.name == "nt" and re.fullmatch(r"[A-Za-z]:", typed):
            typed += "\\"
        path = Path(os.path.expanduser(typed))
        if not path.is_absolute():
            path = (self.directory or Path.home()) / path
        if path.is_dir():
            self.go(path)
            return None
        if path.is_file():
            self.selected = path
            return path
        self.error = f"{path} nicht gefunden"
        return None

    def choice(self) -> Path | None:
        """Die Datei, die „Öffnen“ nimmt: die angeklickte (sie muss zum Dateityp passen - sonst hätte die Liste sie
        nicht gezeigt, nur ein getippter Pfad kann daran vorbei, und der gilt)."""
        return self.selected if self.selected is not None and self.selected.is_file() else None
