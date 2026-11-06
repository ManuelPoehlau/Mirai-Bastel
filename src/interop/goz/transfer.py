"""The effectful GoZ steps: identifiers, writing a send, starting ZBrush, reading the inbox (AD-029 §4). Stdlib only.

- Identifier: `<GoZ project folder>\\<stem>`, the stem from Mirai's own name registry (`names.py`, AD-029 §3), not
  from `GoZMakeObjectPath.exe` (its number followed ZBrush's last export, not the object). A resend of the same
  object reuses its identifier, so ZBrush updates the linked SubTool / Tool.
- Send: `<identifier>.GoZ` (atomic), `GoZ_ObjectList.txt`, `GoZ_Application.txt` = `Mirai` (so ZBrush's next GoZ
  comes back here; only once ZBrush knows Mirai, `install.known_to_zbrush`), then `GoZBrushFromApp.exe` **without `-tmap`** (with it ZBrush
  exports its active Tool instead of importing, E1 T5.2). Not waited for.
- Inbox: tickets written by `helper.py`; a ticket is claimed by moving it into `done/` first (atomic), so two Mirai
  windows never both take it.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from .files import (
    APP_FOLDER_NAME,
    MANIFEST_SUFFIX,
    GozPaths,
    GozSetupError,
    ansi_encoding,
    sha256,
    write_bytes_atomic,
    write_goz_list,
    write_text_atomic,
)
from .format import GozFormatError, GozMesh, parse_goz

Runner = Callable[[Sequence[str], Path], "subprocess.Popen"]


def default_runner(command: Sequence[str], cwd: Path):
    """As the E1 probe started the utilities (verified on the reference PC): plain `Popen`, no creation flags."""
    return subprocess.Popen(list(command), cwd=str(cwd))


def manifest_path(directory: Path, identifier: str) -> Path:
    """Manifests live in Mirai's own folder (`goz/manifests/`), never in ZBrush's project folder: Mirai writes nothing
    there but the `.GoZ` itself."""
    key = os.path.normcase(identifier.replace("\\", "/"))
    return Path(directory) / (sha256(key.encode("utf-8"))[:32] + MANIFEST_SUFFIX)


def write_manifest(directory: Path, identifier: str, manifest_json: str) -> None:
    write_text_atomic(manifest_path(directory, identifier), manifest_json)


def write_send(paths: GozPaths, identifier: str, data: bytes, more: Sequence[tuple[str, bytes]] = ()) -> Path:
    """Every `.GoZ` first, then one `GoZ_ObjectList.txt` naming all of them (P3c: base and targets in one transfer;
    E3 T9.5: ZBrush 2022.0.8 takes both)."""
    target = Path(identifier + ".GoZ")
    write_bytes_atomic(target, data)
    for other, payload in more:
        write_bytes_atomic(Path(other + ".GoZ"), payload)
    write_goz_list(paths.object_list, [identifier, *(other for other, _ in more)])
    write_text_atomic(paths.application_file, APP_FOLDER_NAME, encoding=ansi_encoding(), newline="")
    return target


def launch_zbrush(paths: GozPaths, *, runner: Runner = default_runner):
    exe = paths.utility("GoZBrushFromApp")
    if not exe.is_file():
        raise GozSetupError(f"{exe} missing: is GoZ installed?")
    return runner([str(exe)], paths.gozbrush)  # never `-tmap` (E1 T5.2)


def launch_zbrush_with_script(
    paths: GozPaths,
    identifiers: Sequence[str],
    script_dir: Path,
    *,
    runner: Runner = default_runner,
):
    """Multi-SubTool send: write .ztn files and call ZBrush.exe with the import ZScript (AD-029 §3, option a).
    Tool:Import in ZScript does not write .ztn files, so pre-written ones stay intact."""
    from .zscript import make_import_script, write_ztn_files, zbrush_exe

    project = paths.project_dir()
    objects = [(Path(ident).stem, str(Path(ident + ".GoZ"))) for ident in identifiers]
    write_ztn_files(project, identifiers)
    script_text = make_import_script(objects)
    script_path = Path(script_dir) / "mirai_import.zsc"
    write_text_atomic(script_path, script_text)
    exe = zbrush_exe(paths)
    if not exe.is_file():
        raise GozSetupError(f"{exe} not found: start ZBrush once so it writes GoZ_Config.txt")
    runner([str(exe), str(script_path)], paths.gozbrush)


def read_manifest_text(directory: Path, identifier: str) -> Optional[str]:
    try:
        return manifest_path(directory, identifier).read_text(encoding="utf-8")
    except OSError:
        return None


# -- inbox ------------------------------------------------------------------------------------------------------------


@dataclass
class Received:
    """One object of a claimed ticket: the parsed copy, or why there is none."""

    identifier: str
    goz: Optional[GozMesh]
    error: Optional[str]


class Inbox:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def waiting(self) -> list[Path]:
        try:
            names = sorted(e.name for e in os.scandir(self.directory)
                           if e.is_file() and e.name.startswith("ticket_") and e.name.endswith(".json"))
        except FileNotFoundError:
            return []
        return [self.directory / n for n in names]

    def claim(self, ticket: Path) -> Optional[list[Received]]:
        """Moves the ticket into `done/` and reads its copies (each verified by sha256 and parsed strictly). None if
        another process claimed it first."""
        done = self.directory / "done"
        done.mkdir(parents=True, exist_ok=True)
        claimed = done / ticket.name
        try:
            os.replace(ticket, claimed)
        except FileNotFoundError:
            return None
        try:
            raw = json.loads(claimed.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return [Received(ticket.stem, None, f"unreadable ticket: {exc}")]
        out = []
        for obj in raw.get("objects", []):
            identifier = str(obj.get("identifier", "?"))
            if not obj.get("complete") or not obj.get("copy"):
                out.append(Received(identifier, None, f"transfer incomplete ({obj.get('error') or 'no copy'})"))
                continue
            try:
                data = Path(obj["copy"]).read_bytes()
                if sha256(data) != obj.get("sha256"):
                    raise GozFormatError("the copy does not match its hash")
                out.append(Received(identifier, parse_goz(data), None))
            except (OSError, GozFormatError) as exc:
                out.append(Received(identifier, None, f"{type(exc).__name__}: {exc}"))
        return out
