"""GoZ folders and text files, atomic writes, and the completeness rule (AD-029 §4; E1 README §2.2, §7, §11).

Stdlib only (ZBrush's helper process imports it). Paths verified on the reference PC (E1-Q5): root
`C:\\Users\\Public\\Pixologic`, `GoZBrush\\` (utilities and list files), `GoZApps\\<App>\\`, `GoZProjects\\Default\\`.
GoZ list files are ANSI with CRLF, as Windows programs write them; ZBrush writes identifiers with forward slashes,
Mirai with backslashes - both work (E1).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from .format import GozFormatError, parse_goz

IS_WINDOWS = os.name == "nt"
APP_FOLDER_NAME = "Mirai"  # D12 (Manu, 2026-11-05); a GoZ application id has no spaces (SDK IV)
APP_DISPLAY_NAME = "Mirai"
MANIFEST_SUFFIX = ".mirai-goz.json"


class GozSetupError(RuntimeError):
    """The GoZ installation is missing or not as expected (shown in the status line)."""


def root_candidates() -> list[Path]:
    public = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    return [public / "Pixologic", public / "Documents" / "Maxon", public / "Maxon"]


def find_root(explicit: Optional[os.PathLike] = None) -> Path:
    """`explicit`, else `MIRAI_GOZ_ROOT`, else the first candidate with a `GoZBrush` folder."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("MIRAI_GOZ_ROOT")
    if env:
        return Path(env)
    for candidate in root_candidates():
        if (candidate / "GoZBrush").is_dir():
            return candidate
    raise GozSetupError("no GoZ folder found (C:\\Users\\Public\\Pixologic\\GoZBrush): start ZBrush once")


def ansi_encoding() -> str:
    return "mbcs" if IS_WINDOWS else "utf-8"


def read_text(path: Path) -> Optional[str]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    for encoding in ("utf-8-sig", ansi_encoding(), "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1", errors="replace")


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_text_atomic(path: Path, text: str, *, encoding: str = "utf-8", newline: str = "\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding=encoding, newline=newline) as handle:
        handle.write(text)
    os.replace(tmp, path)


def write_json_atomic(path: Path, value) -> None:
    write_text_atomic(path, json.dumps(value, ensure_ascii=False) + "\n")


def write_goz_list(path: Path, lines: Sequence[str]) -> None:
    write_text_atomic(path, "\r\n".join(lines) + "\r\n" if lines else "\r\n", encoding=ansi_encoding(), newline="")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def same_identifier(a: str, b: str) -> bool:
    """ZBrush's identifiers use `/`, Mirai's `\\`; Windows paths compare case-insensitively."""
    return os.path.normcase(a.replace("\\", "/")) == os.path.normcase(b.replace("\\", "/"))


@dataclass(frozen=True)
class GozPaths:
    root: Path

    @property
    def gozbrush(self) -> Path:
        return self.root / "GoZBrush"

    @property
    def app_dir(self) -> Path:
        return self.root / "GoZApps" / APP_FOLDER_NAME

    @property
    def object_list(self) -> Path:
        return self.gozbrush / "GoZ_ObjectList.txt"

    @property
    def application_file(self) -> Path:
        return self.gozbrush / "GoZ_Application.txt"

    @property
    def object_path_file(self) -> Path:
        return self.gozbrush / "GoZ_ObjectPath.txt"

    def utility(self, name: str) -> Path:
        return self.gozbrush / (name + (".exe" if IS_WINDOWS else ""))

    def project_dir(self) -> Path:
        text = read_text(self.gozbrush / "GoZ_ProjectPath.txt")
        line = text.strip().splitlines()[0].strip() if text and text.strip() else ""
        return Path(line) if line else self.root / "GoZProjects" / "Default"

    def read_object_list(self) -> list[str]:
        return [line.strip() for line in (read_text(self.object_list) or "").splitlines() if line.strip()]


def exclusive_open(path: Path) -> str:
    """Windows: open with share mode 0 ("ok" or "blocked"); elsewhere "n/a". Diagnostic only (E1 README §7.5)."""
    if not IS_WINDOWS:
        return "n/a"
    try:
        import ctypes
        from ctypes import wintypes

        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                  wintypes.DWORD, wintypes.HANDLE]
        k.CreateFileW.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = k.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
        if handle is None or handle == (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1:
            return f"blocked (error {ctypes.get_last_error()})"
        k.CloseHandle(handle)
        return "ok"
    except Exception as exc:  # a diagnostic never fails the transfer
        return f"error {exc}"


# -- completeness (E1 README §7) ---------------------------------------------------------------------------------------


@dataclass
class Snapshot:
    identifier: str
    copy: Optional[str] = None
    sha256: Optional[str] = None
    complete: bool = False
    error: Optional[str] = None
    exclusive_open: Optional[str] = None
    attempts: int = 0

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def snapshot_object(
    identifier: str,
    staging: Path,
    index: int,
    *,
    settle: float = 1.0,
    deadline: float = 10.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Snapshot:
    """§7 rule: copy -> strict parse of the copy -> wall-clock quiet period -> re-hash the original (must be unchanged),
    plus the exclusive-open diagnostic; any failure retries with back-off until `deadline` seconds have passed. Every
    later step works on the copy; ZBrush's file is only read."""
    source = Path(identifier + ".GoZ")
    snap = Snapshot(identifier)
    start, wait = clock(), 0.25
    while True:
        snap.attempts += 1
        try:
            data = source.read_bytes()
            digest = sha256(data)
            parse_goz(data)
            sleep(settle)
            if sha256(source.read_bytes()) != digest:
                raise GozFormatError("the file changed during the quiet period")
            target = staging / f"{index:02d}_{source.stem}.GoZ"
            write_bytes_atomic(target, data)
            snap.copy, snap.sha256, snap.complete, snap.error = str(target), digest, True, None
            snap.exclusive_open = exclusive_open(source)
            return snap
        except (OSError, GozFormatError) as exc:
            snap.error = f"{type(exc).__name__}: {exc}"
        if clock() - start + wait > deadline:
            return snap
        sleep(wait)
        wait = min(wait * 2, 2.0)


def new_ticket_name(ns: Optional[int] = None) -> str:
    ns = time.time_ns() if ns is None else ns
    return f"ticket_{ns:020d}_{os.getpid()}"


def remove_tree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
