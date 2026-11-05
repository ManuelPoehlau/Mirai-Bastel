"""Registers Mirai as a GoZ application: `<root>\\GoZApps\\Mirai\\` (D8/D12, AD-029 §4; E1-Q1/Q2).

Only on the artist's explicit command (SPACE menu row). Writes `GoZ_Info.txt` and three `.bat` commands (cmd.exe reads
them in the OEM code page, CRLF): `Locate.bat` offers `Mirai.cmd` as the application path, `Init.bat` reports success,
`Edit.bat` runs `helper.py` with this Mirai's Python. A folder without the marker file is never touched; reinstalling
replaces only our own. ZBrush lists a new app only after a restart (E1). No flip options in `GoZ_Info.txt`: the bridge
flips in the file (E1 README §11). The artist's ZBrush GoZ preferences are never changed.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

from .files import APP_DISPLAY_NAME, IS_WINDOWS, GozPaths, GozSetupError, write_text_atomic

MARKER = ".mirai_goz_app"
HELPER = Path(__file__).resolve().parent / "helper.py"

GOZ_INFO = f'''NAME\t\t= "{APP_DISPLAY_NAME}"
GOZ_VERSION\t= 1
EXTENSION\t= ".GoZ"
TAMPLATE\t= "GoZ Complete Binary.GoZ"
LOCATE_COMMAND\t= "Locate.bat"
INIT_COMMAND\t= "Init.bat"
EDIT_COMMAND\t= "Edit.bat"
'''


def _batch_encoding() -> str:
    if IS_WINDOWS:
        import ctypes

        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    return "utf-8"


def batch_files(paths: GozPaths, inbox: Path, python: str) -> dict[str, str]:
    app = paths.app_dir
    return {
        "Locate.bat": (
            "@echo off\nrem Mirai GoZ - Locate utility: offers Mirai.cmd as the application path.\n"
            f'> "{app / "GoZ_AppPathList.txt"}" echo {app / "Mirai.cmd"}\nexit /b 0\n'
        ),
        "Init.bat": (
            "@echo off\nrem Mirai GoZ - Install utility: nothing to install; an empty log means success.\n"
            f'type nul > "{app / "GoZ_InstallLog.txt"}"\nexit /b 0\n'
        ),
        "Edit.bat": (
            "@echo off\nrem Mirai GoZ - Editing utility: hands the transfer to a running Mirai (ticket); never starts it.\n"
            f'"{python}" -I "{HELPER}" --root "{paths.root}" --inbox "{inbox}" -- %*\nexit /b %ERRORLEVEL%\n'
        ),
        "Mirai.cmd": (
            "@echo off\necho Mirai is started from its own folder (python src\\main.py); ZBrush only hands it\n"
            "echo transfers. Start Mirai, then press GoZ again - or leave it: Mirai picks up waiting transfers.\n"
            "pause\n"
        ),
    }


def is_installed(paths: GozPaths) -> bool:
    return (paths.app_dir / MARKER).is_file()


def known_to_zbrush(paths: GozPaths) -> bool:
    """True once ZBrush has taken Mirai as a GoZ application: after the restart that lists it and the artist's pick with
    **R**, ZBrush writes the chosen application path into `GoZApps\\Mirai\\GoZ_Config.txt` (SDK IV; E1: ZBrush ran
    Locate/Init on that pick). `install` never writes that file and a reinstall removes it, so it cannot be stale.
    Until then a send must not name Mirai as the active GoZ application: ZBrush 2022.0.8 crashed when a send named
    `Mirai` while `GoZApps\\Mirai` did not exist (Manu, 2026-11-05)."""
    return is_installed(paths) and (paths.app_dir / "GoZ_Config.txt").is_file()


def install(paths: GozPaths, inbox: Path, *, python: str = sys.executable) -> Path:
    if not paths.gozbrush.is_dir():
        raise GozSetupError(f"{paths.gozbrush} missing: is GoZ installed? (ZBrush: Preferences > GoZ > Force Reinstall)")
    app = paths.app_dir
    if app.exists():
        if not (app / MARKER).is_file():
            raise GozSetupError(f"{app} exists and is not Mirai's: not touched")
        shutil.rmtree(app)
    encoding = _batch_encoding()
    files = batch_files(paths, inbox, python)
    for name, text in files.items():
        try:
            text.encode(encoding)
        except UnicodeEncodeError as exc:
            raise GozSetupError(f"{name}: a path cannot be written in the console code page {encoding}: {exc}") from None
    app.mkdir(parents=True)
    for name, text in files.items():
        write_text_atomic(app / name, text.replace("\n", "\r\n"), encoding=encoding, newline="")
    write_text_atomic(app / "GoZ_Info.txt", GOZ_INFO.replace("\n", "\r\n"), newline="")
    write_text_atomic(app / MARKER, json.dumps({"installed": time.strftime("%Y-%m-%d %H:%M:%S"), "python": python,
                                                "helper": str(HELPER), "inbox": str(inbox), "pid": os.getpid()}))
    return app


def uninstall(paths: GozPaths) -> bool:
    app = paths.app_dir
    if not app.exists():
        return False
    if not (app / MARKER).is_file():
        raise GozSetupError(f"{app} is not Mirai's: not removed")
    shutil.rmtree(app)
    return True
