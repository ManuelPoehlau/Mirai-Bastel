"""Persistence for the Artist-Truth Input Binding Config.

Isolation note: this module touches exactly one file —
``artist_input_truth.json`` next to it. It never reads or writes anything
under ``src/``, ``playground/`` or any ``keymap.json``. It has no import
dependency on ``src.mirai.interaction`` or any other runtime module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inventory import CATEGORY_ORDER, DEFAULT_INVENTORY

SCHEMA_VERSION = 1
CONFIG_FILENAME = "artist_input_truth.json"

_NOTE = (
    "Artist-owned interaction language for Mirai-Bastel. This file is the "
    "Artist Truth (see tools/input_binding_config/README.md). It is "
    "independent of src/mirai/interaction/commands.py and of any "
    "keymap.json — 'runtime_ref' is an informational reference only, not a "
    "dependency. Nothing in this file is wired into the running "
    "application yet."
)


def config_path(base_dir: Path | None = None) -> Path:
    base = base_dir or Path(__file__).resolve().parent
    return base / CONFIG_FILENAME


def _seed_entry(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "label": item["label"],
        "category": item["category"],
        "binding": "",
        "runtime_ref": item.get("runtime_ref"),
        "notes": "",
    }


def _fresh_document() -> dict[str, Any]:
    return {
        "artistTruthVersion": SCHEMA_VERSION,
        "note": _NOTE,
        "bindings": [_seed_entry(item) for item in DEFAULT_INVENTORY],
    }


def load_or_seed(path: Path | None = None) -> dict[str, Any]:
    """Loads the artist truth file, creating it from the seed inventory
    if it does not exist yet.

    If the file already exists, any semantic id present in
    ``inventory.DEFAULT_INVENTORY`` but missing from the file is appended
    (binding empty). Existing entries — including their bindings and any
    ids no longer in the current inventory — are preserved as-is. This
    tool never silently deletes an artist decision.
    """
    p = path or config_path()
    if not p.is_file():
        doc = _fresh_document()
        save(doc, p)
        return doc

    doc = json.loads(p.read_text(encoding="utf-8"))
    doc.setdefault("artistTruthVersion", SCHEMA_VERSION)
    doc.setdefault("note", _NOTE)
    bindings = doc.setdefault("bindings", [])
    known_ids = {entry["id"] for entry in bindings}
    changed = False
    for item in DEFAULT_INVENTORY:
        if item["id"] not in known_ids:
            bindings.append(_seed_entry(item))
            changed = True
    if changed:
        save(doc, p)
    return doc


def save(doc: dict[str, Any], path: Path | None = None) -> None:
    p = path or config_path()
    p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def category_sort_key(category: str) -> int:
    try:
        return CATEGORY_ORDER.index(category)
    except ValueError:
        return len(CATEGORY_ORDER)


def find_conflicts(bindings: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Returns {normalized_binding: [ids...]} for every binding string used
    by more than one function. Empty bindings are ignored. Reporting only —
    never used to block or reject anything.
    """
    by_binding: dict[str, list[str]] = {}
    for entry in bindings:
        value = (entry.get("binding") or "").strip()
        if not value:
            continue
        key = value.lower()
        by_binding.setdefault(key, []).append(entry["id"])
    return {k: v for k, v in by_binding.items() if len(v) > 1}
