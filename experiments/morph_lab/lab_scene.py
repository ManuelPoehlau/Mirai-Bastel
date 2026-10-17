"""The lab's scene file: base + morph target, written once, then opened like any scene file.

The lab never adds objects at runtime (no `AddObjectCommand`, no History entry, review CLAUDE-001
R-5/F-12). Its start scene is an ordinary format-v2 file (`core.serialization`) with two objects:

- the base, named after the asset, the edit object, identity placement;
- the target `"<asset> · Ziel 1"`, an ID-identical copy of the base's Mesh
  (`Mesh.from_state(base.export_state())`), NORMAL, placed beside the base along +X.

`run.py` opens it through `init_scene` + `SceneFiles.load` (→ `load_scene`), as `src/main.py`
opens a scene file (AD-013 H7 note "Second user"); Ctrl+S writes back into the same file. The file
lives in `scenes/morph_lab/`, a subfolder the production SPACE menu does not list (review F-6).
Names and placement are `PROVISIONAL`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from core.ids import ObjectId
from core.mesh import Mesh
from core.scene import ObjectTransform, Scene, SceneObject
from core.serialization import scene_from_json, scene_to_json
from loaders.assets import asset_names, asset_path
from mirai.scene_factory import build_core_scene_from_obj

from ._paths import REPO_ROOT

DEFAULT_ASSET = "head_basemesh"
#: The lab's own scene folder (git-ignored with `scenes/`).
DEFAULT_SCENE_DIR = REPO_ROOT / "scenes" / "morph_lab"
SCENE_SUFFIX = ".mirai.json"
TARGET_SUFFIX = " · Ziel 1"
#: `PROVISIONAL`: centre distance of the target from the base, in base widths along X.
TARGET_SPACING = 1.25


class UnknownAssetError(LookupError):
    """Asset name is not registered in `loaders.assets.asset_names()`."""


class LabSceneError(RuntimeError):
    """The lab's scene file cannot be used (missing objects, ambiguous names, load error)."""


def resolve_asset_name(name: str) -> str:
    """Returns `name` or raises `UnknownAssetError` listing all valid names."""
    valid = asset_names()
    if name not in valid:
        raise UnknownAssetError(f"Unbekanntes Asset {name!r}. Gültige Namen: {', '.join(valid)}")
    return name


def target_name(asset_name: str) -> str:
    return asset_name + TARGET_SUFFIX


def scene_path(asset_name: str, directory: str | Path = DEFAULT_SCENE_DIR) -> Path:
    return Path(directory) / f"{asset_name}{SCENE_SUFFIX}"


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def build_start_scene(asset_name: str) -> Scene:
    """Base + ID-identical target, as described in the module docstring."""
    resolve_asset_name(asset_name)
    base_mesh = build_core_scene_from_obj(str(asset_path(asset_name))).mesh
    return build_pair_scene(asset_name, base_mesh)


def build_pair_scene(name: str, base_mesh: Mesh) -> Scene:
    """Base (named `name`, a copy of `base_mesh`) + ID-identical target. Shared by the asset start
    and the bridge from `src/main.py` (`--von`)."""
    base_mesh = Mesh.from_state(base_mesh.export_state())
    target_mesh = Mesh.from_state(base_mesh.export_state())
    xs = [base_mesh.vertex_position(v)[0] for v in base_mesh.all_vertex_ids()]
    width = (max(xs) - min(xs)) if xs else 1.0
    placement = ObjectTransform(translation=(TARGET_SPACING * (width or 1.0), 0.0, 0.0))
    base = SceneObject(ObjectId(0), base_mesh, name=name)
    target = SceneObject(ObjectId(1), target_mesh, name=target_name(name), transform=placement)
    return Scene.from_objects([base, target], edit_object_id=base.id, object_id_counter=2)


def write_start_scene(asset_name: str, path: Path) -> Path | None:
    """Writes a fresh start scene to `path`. An existing file is kept as `<name>.bak` (one backup,
    review F-13); returns the backup path or None."""
    return _write_scene(build_start_scene(asset_name), path)


def write_pair_scene(name: str, mesh: Mesh, path: Path) -> Path | None:
    """Same as `write_start_scene`, for a mesh sent from `src/main.py` instead of an asset."""
    return _write_scene(build_pair_scene(name, mesh), path)


def read_sent_object(path: str | Path) -> tuple[str, Mesh]:
    """Name and mesh of the object `src/morph_bridge.py` wrote (the file's edit object). Its
    placement is dropped: the lab's base always sits at the identity."""
    try:
        scene = scene_from_json(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # unreadable or malformed file: one visible line
        raise LabSceneError(f"Gesendete Szene {str(path)!r} nicht lesbar: {exc}") from exc
    obj = scene.edit_object
    return obj.name, obj.mesh


def safe_file_stem(name: str) -> str:
    """A file name part from an object name (`scene_path` takes it as the asset name)."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "objekt"


def _write_scene(scene: Scene, path: Path) -> Path | None:
    text = scene_to_json(scene)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = backup_path(path)
        os.replace(path, backup)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return backup


def resolve_pair(scene, asset_name: str) -> tuple:
    """The ObjectIds of base and target by the names the lab wrote; exactly one object per name,
    otherwise `LabSceneError` (names are not unique in general, review F-6). Resolved once after
    the load; ObjectIds are session-local (`replace_scene` re-allocates them)."""
    wanted = {"Basis": asset_name, "Ziel": target_name(asset_name)}
    found = {}
    for role, name in wanted.items():
        ids = [oid for oid, obj in scene.objects.items() if obj.name == name]
        if len(ids) != 1:
            raise LabSceneError(
                f"{role} {name!r}: {len(ids)} Objekte mit diesem Namen in der Szene (erwartet genau 1)"
            )
        found[role] = ids[0]
    return found["Basis"], found["Ziel"]
