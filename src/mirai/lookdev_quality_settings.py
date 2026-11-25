"""The LookDev quality settings (AD-040 §8.2, LD-3a): a machine setting, not a scene or view value.

Quality belongs to the PC (F7): the settings live in `~/.mirai_bastel/lookdev_quality.json` (the state directory the
file browser already uses), read once at start and written on every change - never in `view.lookdev`, the scene file
or Undo. `load(path)` returns the defaults for a missing or unreadable file and for any bad value (each key on its own);
an unknown key is ignored. `save(path, settings)` writes atomically (a temporary file, then `os.replace`) and returns
False instead of raising when the disk refuses. `main.py` passes the path; headless tests use a temporary directory, and
`path=None` keeps the settings in memory only.

Content: `{"tier": "auto", "refine": false, "idle_tier": "hoch", "wait": 0.3}`; LD-3a adds `"drag_updates"` - the key
map's policy while a caster is dragged (Q-LD3-1, open until the reference-PC run; "every" = today's map), shown under
„Mehr“ for the practical test.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from viewport.lookdev_quality import (DEFAULT_DRAG_UPDATES, IDLE_TIERS, SHADOW_UPDATES, TIERS, WAIT_DEFAULT, WAIT_MAX,
                                      WAIT_MIN)

FILE_NAME = "lookdev_quality.json"


@dataclass(frozen=True)
class QualitySettings:
    tier: str = "auto"
    refine: bool = False  # F-R2: off by default
    idle_tier: str = "hoch"
    wait: float = WAIT_DEFAULT
    drag_updates: str = DEFAULT_DRAG_UPDATES

    def __post_init__(self) -> None:
        if self.tier not in TIERS:
            raise ValueError(f"tier one of {TIERS}")
        if self.idle_tier not in IDLE_TIERS:
            raise ValueError(f"idle_tier one of {IDLE_TIERS}")
        if self.drag_updates not in SHADOW_UPDATES:
            raise ValueError(f"drag_updates one of {SHADOW_UPDATES}")
        if not isinstance(self.refine, bool):
            raise ValueError("refine: true or false")
        number = isinstance(self.wait, (int, float)) and not isinstance(self.wait, bool)
        if not number or not WAIT_MIN <= self.wait <= WAIT_MAX:
            raise ValueError(f"wait: {WAIT_MIN} .. {WAIT_MAX} s")

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULTS = QualitySettings()


def default_path() -> Path:
    """`~/.mirai_bastel/lookdev_quality.json` (the per-user state directory, `gui.menus`)."""
    return Path.home() / ".mirai_bastel" / FILE_NAME


def from_dict(data) -> QualitySettings:
    """The settings of `data`: every known key whose value is valid, the default otherwise; unknown keys ignored."""
    settings = DEFAULTS
    if not isinstance(data, dict):
        return settings
    for name in DEFAULTS.as_dict():
        if name not in data:
            continue
        value = data[name]
        if name == "wait" and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        try:
            settings = replace(settings, **{name: value})
        except (TypeError, ValueError):
            continue
    return settings


def load(path: str | Path | None) -> QualitySettings:
    """The settings stored at `path` (None, a missing or unreadable file: the defaults)."""
    if path is None:
        return DEFAULTS
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULTS
    return from_dict(data)


def save(path: str | Path | None, settings: QualitySettings) -> bool:
    """Write `settings` to `path` (None: nothing). True = written."""
    if path is None:
        return False
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(settings.as_dict(), indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        return False
    return True
