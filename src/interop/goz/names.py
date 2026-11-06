"""Mirai's own GoZ names (AD-029 §3, §5): one stable identifier per (object, base or morph target). Stdlib only.

Why Mirai names its SubTools itself instead of asking `GoZMakeObjectPath.exe` (Manu, 2026-11-06; evidence in AD-029
§3): the tool's number is not a function of what Mirai can see. In the 29 E1-E3 calls (`experiments/goz_probe/
captures/*_send_*/send_log.json`) `E1_A` came back unnumbered 15 times although `E1_A.GoZ` lay in
`GoZProjects\\Default` every time (and ZBrush had written it on three returns), while `E1_C` (17:44) and `E1_C_P1_G`
(22:33) came back as `E1_C1` / `E1_C_P1_G1` - each time the name ZBrush had exported last. Asking it again at every
Mirai start therefore gave a new name for the same object, i.e. a new Tool instead of an update.

Rules:

- **Stable:** an entry is keyed by (saved scene file, `ObjectId`, `LayerId` or None) - or, for an unsaved scene, by
  (session, `ObjectId`, `LayerId`). A resend, also after a Mirai or ZBrush restart, uses the entry's stem, so ZBrush
  updates the same Tool.
- **Readable:** the stem is `short_name(<object>)` or `short_name(<object>_<target>)`; only a clash gives `_2`, `_3`, ...
  A stem clashes when another entry owns it, or when `<stem>.GoZ` lies in the project folder and is not Mirai's (no
  entry and no Mirai manifest for it): Mirai writes into no file it did not create (AD-029 §3).
- **Gone object or target** (Manu, 2026-11-06: targets deleted and made again got `_2`, then `_3`): an entry of the
  current scene file (or this session) whose object or morph target no longer exists frees its stem; the next object
  or target of that wish name takes it over (and its Tool in ZBrush).
- **Unsaved scene after a restart:** an entry of an unsaved scene from another session with the same wish stem is taken
  over (the same object sent again after a restart updates its Tool instead of counting up). Returns of the old
  session still only become new objects (the manifest names the old session, D11).
- **ZBrush renamed a Tool** (a return linked by topology, AD-029 §5): the entry follows ZBrush's name (`stem`), the old
  one is kept in `former`, so the next send updates the Tool the artist works on.
- **Older manifests** (sent before this registry existed, by `GoZMakeObjectPath` names): a Mirai manifest for exactly
  `<project>\\<stem>` makes that stem Mirai's own; its object is taken from the manifest.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .files import write_text_atomic

REGISTRY_FILE = "names.json"
#: 2 (2026-11-06): a version-1 file is read as empty once - its entries of deleted targets held the plain names; the
#: manifests on disk then give every stem back to its live object (`legacy`) and free those of gone ones (`dead`)
REGISTRY_VERSION = 2
#: the oldest entries beyond this are forgotten (their stems become free again)
MAX_ENTRIES = 1000


def scene_key(scene_path: Optional[os.PathLike | str]) -> Optional[str]:
    return None if scene_path is None else os.path.normcase(str(Path(scene_path).resolve()))


def fold(stem: str) -> str:
    """Windows file names compare case-insensitively."""
    return stem.casefold()


def stem_of(identifier: str) -> str:
    return identifier.replace("\\", "/").rsplit("/", 1)[-1]


def with_stem(identifier: str, stem: str) -> str:
    """`identifier` with its last part replaced (same folder, same separator style)."""
    cut = max(identifier.rfind("/"), identifier.rfind("\\"))
    return identifier[: cut + 1] + stem


@dataclass
class NameEntry:
    stem: str
    title: str
    scene: Optional[str]
    session: str
    object_id: int
    layer: Optional[int]
    former: list[str] = field(default_factory=list)
    updated: float = 0.0

    def owns(self, stem: str) -> bool:
        return fold(stem) == fold(self.stem) or any(fold(stem) == fold(s) for s in self.former)

    def is_for(self, scene: Optional[str], session: str, object_id: int, layer: Optional[int]) -> bool:
        if self.object_id != object_id or self.layer != layer:
            return False
        if scene is not None and self.scene == scene:
            return True
        return self.session == session and (self.scene is None or self.scene == scene)


class NameRegistry:
    """`<manifest dir>/names.json`, read again before every use (another Mirai window may have written it)."""

    def __init__(self, path: Path, *, clock: Callable[[], float] = time.time) -> None:
        self.path = Path(path)
        self._clock = clock
        self.entries: list[NameEntry] = []
        self.reload()

    def reload(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            entries = [NameEntry(**e) for e in raw.get("entries", [])] if raw.get("version") == REGISTRY_VERSION else []
        except (OSError, ValueError, TypeError):
            entries = []  # missing or unreadable: older manifests still make their stems Mirai's (`allocate`)
        self.entries = entries

    def save(self) -> None:
        self.entries.sort(key=lambda e: e.updated)
        del self.entries[:-MAX_ENTRIES]
        write_text_atomic(self.path, json.dumps({"version": REGISTRY_VERSION,
                                                 "entries": [asdict(e) for e in self.entries]}, ensure_ascii=False))

    def owner(self, stem: str) -> Optional[NameEntry]:
        for entry in self.entries:
            if entry.owns(stem):
                return entry
        return None

    def find(self, scene: Optional[str], session: str, object_id: int, layer: Optional[int]) -> Optional[NameEntry]:
        for entry in reversed(self.entries):
            if entry.is_for(scene, session, object_id, layer):
                return entry
        return None

    def allocate(self, title: str, *, scene: Optional[str], session: str, object_id: int, layer: Optional[int],
                 foreign_file: Callable[[str], bool],
                 legacy: Callable[[str], Optional[NameEntry]] = lambda stem: None,
                 dead: Callable[[NameEntry], bool] = lambda entry: False,
                 max_length: int = 40) -> NameEntry:
        """The entry of (scene / session, object, layer): the existing one, else the first free stem of `title`,
        `title_2`, ... (see the module rules). Not saved: the caller saves once the send is written."""
        now = self._clock()
        entry = self.find(scene, session, object_id, layer)
        if entry is None:
            n = 1
            while entry is None:
                suffix = "" if n == 1 else f"_{n}"
                stem = title[: max_length - len(suffix)] + suffix
                n += 1
                owner = self.owner(stem)
                if owner is None:
                    owner = legacy(stem)
                    if owner is not None:
                        self.entries.append(owner)
                if owner is not None:
                    if owner.is_for(scene, session, object_id, layer) or dead(owner) or (
                            owner.scene is None and owner.session != session and owner.title == title):
                        entry = owner
                        if owner.scene != scene:
                            owner.scene = None  # taken over: no longer the other scene's (`is_for` below decides)
                    continue
                if foreign_file(stem):
                    continue
                entry = NameEntry(stem=stem, title=title, scene=scene, session=session, object_id=object_id,
                                  layer=layer)
                self.entries.append(entry)
        entry.session, entry.object_id, entry.layer, entry.updated = session, object_id, layer, now
        if scene is not None:
            entry.scene = scene
        return entry

    def follow(self, entry: NameEntry, stem: str) -> None:
        """ZBrush returned the entry's Tool under `stem`: the next send goes there."""
        if fold(stem) == fold(entry.stem):
            return
        if entry.stem not in entry.former:
            entry.former.append(entry.stem)
        entry.former = [s for s in entry.former if fold(s) != fold(stem)]
        entry.stem, entry.updated = stem, self._clock()
