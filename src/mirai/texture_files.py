"""Texture files beside a scene (Eye LookDev phase 5, Manu 2026-11-16; AD-026 §7 addendum). Stdlib only.

**Scene-relative paths.** `SceneObject.texture` stays a plain string in the Core; what it means is decided here, in
`src/mirai`, when a scene file is read and written:
- writing: a texture inside the scene file's directory (or below it) is written relative to that directory with `/`
  separators (`Gollum_Head_03_textures/iris_3fa9c2d1e0.png`); every other path is written as it is (absolute);
- reading: a relative path is joined to the scene file's directory, so in memory a texture path is always absolute and
  the viewport, the eye pass and the ZBrush bridge see what they saw before.
A path is absolute on any platform when it is absolute for POSIX or for Windows (`C:\\...`, `\\\\server\\...`), so a
Windows path read on Linux is never joined to the scene directory. A missing texture keeps its path (the round trip
writes the same string back).

AD-035 M1 (2026-11-17): an eye's sclera colour map (`EyeSpec.sclera_texture`) gets the same treatment - resolved on
load, written relative on save and copied beside the scene (`Application._copy_eye_images`).

**Copies beside the scene.** `<scene stem>_textures/` (the ZBrush bridge's convention, `interop.goz.texture`, Manu
2026-11-06). A copy is named by its content (`<stem>_<10 hex of SHA-256>.<ext>`), so the same image is stored once,
and an existing file is never overwritten: a file of that name with other content gets the next free `_2`, `_3` ...
Nothing here deletes a file.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

SCENE_SUFFIX = ".mirai.json"
HASH_LENGTH = 10
_HASHED = re.compile(r"^(?P<stem>.*?)_(?P<hash>[0-9a-f]{%d})(?:_\d+)?$" % HASH_LENGTH)


def is_absolute(path: str) -> bool:
    """Absolute for POSIX or for Windows - a scene file written on either system reads the same on both."""
    return PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute()


def scene_stem(scene_path: str | Path) -> str:
    name = Path(scene_path).name
    return name[: -len(SCENE_SUFFIX)] if name.endswith(SCENE_SUFFIX) else Path(name).stem


def scene_texture_dir(scene_path: str | Path) -> Path:
    """`<scene stem>_textures/` beside the scene file (the same folder `interop.goz.texture.texture_dir` uses)."""
    scene = Path(scene_path)
    return scene.parent / f"{scene_stem(scene)}_textures"


def resolve(texture: str, scene_dir: str | Path) -> str:
    """A texture string as read from a scene file in `scene_dir` -> the absolute path in memory. Absolute strings come
    back unchanged."""
    if is_absolute(texture):
        return texture
    parts = [p for p in re.split(r"[\\/]", texture) if p not in ("", ".")]
    return os.path.normpath(os.path.join(os.path.abspath(scene_dir), *parts))


def to_file(texture: str, scene_dir: str | Path) -> str:
    """An in-memory texture path -> the string a scene file in `scene_dir` stores: relative (`/`) inside the scene
    directory, else unchanged."""
    if not is_absolute(texture) or PureWindowsPath(texture).drive and os.name != "nt":
        return texture  # relative already, or a Windows path on another system: never rewritten here
    base = os.path.normcase(os.path.abspath(scene_dir))
    path = os.path.normcase(os.path.abspath(texture))
    try:
        common = os.path.commonpath([base, path])
    except ValueError:  # another drive
        return texture
    if common != base or path == base:
        return texture
    rel = os.path.relpath(os.path.abspath(texture), os.path.abspath(scene_dir))
    return PurePosixPath(*Path(rel).parts).as_posix()


def inside(path: str | Path, directory: str | Path) -> bool:
    """`path` lies directly in `directory` (compared as absolute, case-folded where the system folds case)."""
    return os.path.normcase(os.path.abspath(Path(path).parent)) == os.path.normcase(os.path.abspath(directory))


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:HASH_LENGTH]


def clean_stem(name: str) -> str:
    """A file-name stem from any name: ASCII letters, digits, `_ . -`; at most 40 characters."""
    return (re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_.") or "texture")[:40]


def hashed_name(stem: str, data: bytes, suffix: str) -> str:
    """`<stem>_<hash>.<suffix>`; a stem that already ends in a hash (a copy of a copy) loses it first."""
    match = _HASHED.match(stem)
    base = match.group("stem") if match else stem
    return f"{clean_stem(base)}_{content_hash(data)}{suffix.lower() or '.img'}"


def store(data: bytes, directory: str | Path, name: str) -> Path:
    """Write `data` as `directory/name` unless that file already holds exactly these bytes. Never overwrites: a file
    of that name with other content makes the next free `<stem>_2`, `_3` ... Returns the file holding `data`. Atomic
    (a neighbour file, then rename); `OSError` when it cannot be written."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stem, suffix = Path(name).stem, Path(name).suffix
    target, counter = directory / name, 2
    while target.exists():
        if target.is_file() and target.read_bytes() == data:
            return target
        target = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, target)
    return target


def copy_into(source: str | Path, directory: str | Path, stem: str | None = None) -> Path:
    """A byte-for-byte copy of `source` in `directory` under its content name (`hashed_name`). `OSError` when the
    source cannot be read or the copy cannot be written."""
    source = Path(source)
    data = source.read_bytes()
    return store(data, directory, hashed_name(stem or source.stem, data, source.suffix))
