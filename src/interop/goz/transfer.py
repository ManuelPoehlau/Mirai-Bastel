"""The effectful GoZ steps: identifiers, writing a send, starting ZBrush, reading the inbox (AD-029 §4). Stdlib only.

- Identifier (SDK III.9, E1-Q8): the short name goes into `GoZBrush\\GoZ_ObjectPath.txt`, `GoZMakeObjectPath.exe` writes
  the unique identifier back (ZBrush appends a number if needed). A resend of the same object reuses its identifier,
  so ZBrush updates the linked SubTool / Tool.
- Send: `<identifier>.GoZ` and `<identifier>.mirai-goz.json` (atomic), `GoZ_ObjectList.txt`, `GoZ_Application.txt` =
  `Mirai` (so ZBrush's next GoZ comes back here), then `GoZBrushFromApp.exe` **without `-tmap`** (with it ZBrush
  exports its active Tool instead of importing, E1 T5.2). Not waited for.
- Inbox: tickets written by `helper.py`; a ticket is claimed by moving it into `done/` first (atomic), so two Mirai
  windows never both take it.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from .files import (
    APP_FOLDER_NAME,
    MANIFEST_SUFFIX,
    GozPaths,
    GozSetupError,
    ansi_encoding,
    read_text,
    sha256,
    write_bytes_atomic,
    write_goz_list,
    write_text_atomic,
)
from .format import GozFormatError, GozMesh, parse_goz

Runner = Callable[[Sequence[str], Path], "subprocess.Popen"]


def default_runner(command: Sequence[str], cwd: Path):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(list(command), cwd=str(cwd), creationflags=flags)


def make_identifier(paths: GozPaths, short: str, *, runner: Runner = default_runner, timeout: float = 5.0,
                    sleep: Callable[[float], None] = time.sleep) -> str:
    exe = paths.utility("GoZMakeObjectPath")
    if not exe.is_file():
        raise GozSetupError(f"{exe} missing: is GoZ installed? (ZBrush: Preferences > GoZ > Force Reinstall)")
    write_text_atomic(paths.object_path_file, short, encoding=ansi_encoding(), newline="")
    proc = runner([str(exe)], paths.gozbrush)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = (read_text(paths.object_path_file) or "").strip()
        if text and text != short:
            return text
        if proc.poll() is not None and proc.poll() != 0:
            break
        sleep(0.02)
    raise GozSetupError(f"GoZMakeObjectPath gave no identifier within {timeout:g} s")


def manifest_path(identifier: str) -> Path:
    return Path(identifier + MANIFEST_SUFFIX)


def write_manifest(identifier: str, manifest_json: str) -> None:
    write_text_atomic(manifest_path(identifier), manifest_json)


def write_send(paths: GozPaths, identifier: str, data: bytes, manifest_json: str) -> Path:
    target = Path(identifier + ".GoZ")
    write_bytes_atomic(target, data)
    write_manifest(identifier, manifest_json)
    write_goz_list(paths.object_list, [identifier])
    write_text_atomic(paths.application_file, APP_FOLDER_NAME, encoding=ansi_encoding(), newline="")
    return target


def launch_zbrush(paths: GozPaths, *, runner: Runner = default_runner):
    exe = paths.utility("GoZBrushFromApp")
    if not exe.is_file():
        raise GozSetupError(f"{exe} missing: is GoZ installed?")
    return runner([str(exe)], paths.gozbrush)  # never `-tmap` (E1 T5.2)


def read_manifest_text(identifier: str) -> Optional[str]:
    try:
        return manifest_path(identifier).read_text(encoding="utf-8")
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
