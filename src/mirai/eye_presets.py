"""Eye look presets (Eye LookDev phase 2, assessment 2026-11-16 §D change 4; `PROVISIONAL`).

A preset is a named bundle of `core.EyeSpec` values. Applying it is one `Application.set_eye` call, so it is one Undo
step and needs no new document entity. The iris image's own values (`fit_pupil`, `fit_limbus`, `hold_outer_color`)
belong to that image and are never part of a preset, so a preset never breaks an eye's iris fit.

The built-in preset is the app's default eye (L0, `eye_object.DEFAULT_EYE`). Presets the artist saves in the Eye Lab
are JSON files in `config/eye_presets/` (`{"name": ..., "values": {...}}`). A file that cannot be read is skipped,
and the reason is reported.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from pathlib import Path

from core import EyeSpec

from .eye_object import DEFAULT_EYE, with_changes

#: Where saved presets live: in the repo, relative to its root (same on Windows and Linux), like `config/keymap.json`.
PRESET_DIR = Path(__file__).resolve().parents[2] / "config" / "eye_presets"
#: The iris image's fit values: they stay with the image, not with a look.
IMAGE_FIELDS = ("fit_pupil", "fit_limbus", "hold_outer_color")
PRESET_FIELDS = tuple(f.name for f in fields(EyeSpec) if f.name not in IMAGE_FIELDS)
BUILTIN_NAME = "Standard (L0)"


@dataclass(frozen=True)
class EyePreset:
    name: str
    values: dict  # PRESET_FIELDS -> value
    builtin: bool = False


def preset_values(spec: EyeSpec) -> dict:
    """The look values of `spec` (no image fit), JSON-ready."""
    raw = spec.to_dict()
    return {name: raw[name] for name in PRESET_FIELDS}


def _validated(values: object) -> dict:
    if not isinstance(values, dict):
        raise ValueError("'values' must be an object")
    unknown = sorted(set(values) - set(PRESET_FIELDS))
    if unknown:
        raise ValueError(f"unknown values {unknown}")
    if not values:
        raise ValueError("no values")
    changes = {k: tuple(v) if k == "limbal_colour" and isinstance(v, list) else v for k, v in values.items()}
    with_changes(DEFAULT_EYE, **changes)  # ValueError on an invalid combination
    return changes


def builtin_presets() -> list[EyePreset]:
    return [EyePreset(BUILTIN_NAME, _validated(preset_values(DEFAULT_EYE)), builtin=True)]


def load_presets(directory: Path = PRESET_DIR) -> tuple[list[EyePreset], list[str]]:
    """(presets, problems): the built-in ones first, then each readable file in `directory` sorted by name. A file
    whose name is taken (built-in or another file) or that is invalid is skipped, with the reason in `problems`."""
    presets = builtin_presets()
    problems: list[str] = []
    if not directory.is_dir():
        return presets, problems
    for path in sorted(directory.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("name"), str) or not raw["name"].strip():
                raise ValueError("needs {\"name\": ..., \"values\": {...}}")
            name = raw["name"].strip()
            if any(p.name == name for p in presets):
                raise ValueError(f"the name {name!r} is taken")
            presets.append(EyePreset(name, _validated(raw.get("values"))))
        except (OSError, ValueError) as exc:  # json.JSONDecodeError is a ValueError
            problems.append(f"{path.name}: {exc}")
    return presets, problems


def file_name(name: str) -> str:
    """A safe file name for a preset name ("Gollum nass" -> "gollum_nass.json")."""
    stem = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not stem:
        raise ValueError("a preset needs a name with letters or digits")
    return stem + ".json"


def save_preset(name: str, spec: EyeSpec, directory: Path = PRESET_DIR) -> Path:
    """Write `spec`'s look values as preset `name`; a saved preset with the same file name is replaced. A built-in name
    is refused (ValueError). Returns the file."""
    name = name.strip()
    if any(p.name == name for p in builtin_presets()):
        raise ValueError(f"{name!r} is a built-in preset")
    path = directory / file_name(name)
    directory.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"name": name, "values": preset_values(spec)}, indent=2)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
