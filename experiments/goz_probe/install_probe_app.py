"""Installs, inspects or removes the E1 GoZ probe application `GoZApps\\MiraiProbe` (README §5, §6 T0/T1).

    python -I experiments/goz_probe/install_probe_app.py --inventory   # read-only: writes captures/inventory.txt
    python -I experiments/goz_probe/install_probe_app.py               # install GoZApps\\MiraiProbe
    python -I experiments/goz_probe/install_probe_app.py --replace     # reinstall (only our own folder)
    python -I experiments/goz_probe/install_probe_app.py --uninstall   # remove GoZApps\\MiraiProbe only

Touches nothing in the GoZ root except `GoZApps\\MiraiProbe` (and only a folder that carries our marker file). The
`.bat` files get the absolute paths of this Python and this repository, so ZBrush needs no PATH.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from goz_probe._paths import EXPERIMENT_DIR, ensure_paths  # noqa: E402

ensure_paths()

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402

from goz_probe.probe_common import (  # noqa: E402
    APP_DISPLAY_NAME,
    APP_FOLDER_NAME,
    APP_MARKER,
    DEFAULT_CAPTURES,
    IS_WINDOWS,
    GozPaths,
    ProbeError,
    find_root,
    kernel32,
    python_info,
    read_pff,
    read_text,
    redact,
    root_candidates,
    stat_record,
    write_text_atomic,
)

TEMPLATE_DIR = EXPERIMENT_DIR / "gozapp" / APP_FOLDER_NAME
APP_PATH = EXPERIMENT_DIR / "probe_app.cmd"
BATCH_TEMPLATES = ("Locate.bat.in", "Init.bat.in", "Edit.bat.in")
TEMPLATE_NAME = "GoZ Complete Binary.GoZ"
TEXT_LIMIT = 64 * 1024


def batch_encoding() -> str:
    """cmd.exe reads .bat files in the OEM code page, not ANSI or UTF-8."""
    if IS_WINDOWS:
        return f"cp{kernel32().GetOEMCP()}"
    return "utf-8"


def render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"@{key}@", value)
    leftover = re.findall(r"@[A-Z_]+@", template)
    if leftover:
        raise ProbeError(f"unfilled template values: {leftover}")
    return template


def install(paths: GozPaths, *, replace: bool, python: str, captures: Path, require_gozbrush: bool = True,
            import_polygroups: bool = False) -> list[Path]:
    if require_gozbrush and not paths.gozbrush.is_dir():
        raise ProbeError(f"{paths.gozbrush} does not exist: is GoZ installed? (ZBrush: Preferences > GoZ > Force Reinstall)")
    app_dir = paths.app_dir
    if app_dir.exists():
        if not (app_dir / APP_MARKER).is_file():
            raise ProbeError(f"{app_dir} exists and is not ours (no {APP_MARKER}): not touched")
        if not replace:
            raise ProbeError(f"{app_dir} is already installed (use --replace to reinstall it)")
        shutil.rmtree(app_dir)
    values = {
        "PYTHON": python,
        "PROBE": str(EXPERIMENT_DIR),
        "ROOT": str(paths.root),
        "APPDIR": str(app_dir),
        "APP_PATH": str(APP_PATH),
    }
    encoding = batch_encoding()
    rendered = {}
    for name in BATCH_TEMPLATES:
        text = render((TEMPLATE_DIR / name).read_text(encoding="utf-8"), values)
        try:
            text.encode(encoding)
        except UnicodeEncodeError as exc:
            raise ProbeError(f"{name}: a path cannot be written in the console code page {encoding}: {exc}") from None
        rendered[name[: -len(".in")]] = text
    captures.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True)
    written = []
    for name, text in rendered.items():
        target = app_dir / name
        write_text_atomic(target, "\r\n".join(text.splitlines()) + "\r\n", encoding=encoding, newline="")
        written.append(target)
    info = app_dir / "GoZ_Info.txt"
    shutil.copyfile(TEMPLATE_DIR / "GoZ_Info.txt", info)
    if import_polygroups:  # E2 variant: the SDK's GoZ_Info option, effect unknown
        with open(info, "ab") as handle:
            handle.write(b"IMPORT_POLYGROUPS\t= TRUE\r\n")
    written.append(info)
    marker = app_dir / APP_MARKER
    write_text_atomic(
        marker,
        json.dumps({"installed": time.strftime("%Y-%m-%d %H:%M:%S"), "values": values, "python": python_info()}, indent=2),
    )
    written.append(marker)
    return written


def uninstall(paths: GozPaths) -> bool:
    app_dir = paths.app_dir
    if not app_dir.exists():
        return False
    if not (app_dir / APP_MARKER).is_file():
        raise ProbeError(f"{app_dir} is not ours (no {APP_MARKER}): not removed")
    shutil.rmtree(app_dir)
    return True


def _listing(folder: Path, depth: int, indent: str = "  ", limit: int = 60) -> list[str]:
    lines = []
    try:
        entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as exc:
        return [f"{indent}(cannot list: {exc})"]
    files = [e for e in entries if not e.is_dir()]
    if len(files) > limit:
        files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        lines.append(f"{indent}({len([e for e in entries if not e.is_dir()])} files, newest {limit} shown)")
    for entry in [e for e in entries if e.is_dir()] + files:
        if entry.is_dir():
            lines.append(f"{indent}{entry.name}/")
            if depth > 1:
                lines.extend(_listing(entry, depth - 1, indent + "  ", limit))
        else:
            st = entry.stat()
            lines.append(f"{indent}{entry.name}  {st.st_size} B  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}")
    return lines


def inventory(root_arg=None) -> str:
    lines = [f"E1 inventory {time.strftime('%Y-%m-%d %H:%M:%S')}", f"python: {python_info()}", "", "GoZ root candidates:"]
    for candidate in root_candidates():
        lines.append(f"  {candidate}: {'exists' if candidate.exists() else 'missing'}"
                     + (", has GoZBrush" if (candidate / 'GoZBrush').is_dir() else ""))
    try:
        root = find_root(root_arg)
    except ProbeError as exc:
        lines.append(f"\nNO ROOT: {exc}")
        return "\n".join(lines) + "\n"
    paths = GozPaths(root)
    lines += ["", f"root used: {root}", "", "tree (3 levels):"] + _listing(root, 3)
    lines += ["", "GoZBrush text files:"]
    for path in sorted(paths.gozbrush.glob("*.txt")) if paths.gozbrush.is_dir() else []:
        if path.name == "GoZ_Help.txt":
            lines.append(f"--- {path.name}: {stat_record(path)} (help text, not shown)")
            continue
        text = read_text(path) or ""
        lines.append(f"--- {path.name} ({len(text)} chars)")
        lines.append(text[:TEXT_LIMIT].rstrip("\r\n"))
    lines += ["", "GoZBrush utilities:"]
    for name in ("GoZBrushFromApp", "GoZMakeObjectPath", "GoZLocateApp"):
        exe = paths.gozbrush / f"{name}.exe"
        lines.append(f"  {exe}: {stat_record(exe)}")
    lines += ["", "GoZApps:"]
    for app in sorted(paths.apps.iterdir()) if paths.apps.is_dir() else []:
        if not app.is_dir():
            continue
        lines.append(f"--- {app.name}/  files: {sorted(p.name for p in app.iterdir())}")
        for name in ("GoZ_Info.txt", "GoZ_Config.txt"):
            if (app / name).is_file():
                lines.append(f"    {name}: {read_pff(app / name)}")
    zbrush = read_pff(paths.config_file).get("PATH")
    lines += ["", f"ZBrush PATH (GoZBrush/GoZ_Config.txt): {zbrush}"]
    if zbrush:
        templates = Path(zbrush).parent / "ZStartup" / "ExportTamplates"
        lines.append(f"export templates folder: {templates} ({'exists' if templates.is_dir() else 'missing'})")
        if templates.is_dir():
            names = sorted(p.name for p in templates.iterdir())
            lines.append(f"  {names}")
            lines.append(f"  '{TEMPLATE_NAME}': {'FOUND' if TEMPLATE_NAME in names else 'MISSING'}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", help="GoZ root (default: C:\\Users\\Public\\Pixologic or a Maxon location)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--inventory", action="store_true", help="read-only report into captures/inventory.txt")
    mode.add_argument("--uninstall", action="store_true", help=f"remove GoZApps\\{APP_FOLDER_NAME} (only ours)")
    parser.add_argument("--replace", action="store_true", help="reinstall over our own earlier installation")
    parser.add_argument("--python", default=sys.executable, help="python.exe the Edit command runs (default: this one)")
    parser.add_argument("--captures", type=Path, default=DEFAULT_CAPTURES)
    parser.add_argument("--import-polygroups", action="store_true",
                        help="E2 variant: add IMPORT_POLYGROUPS = TRUE to GoZ_Info.txt (restart ZBrush afterwards)")
    args = parser.parse_args(argv)
    try:
        if args.inventory:
            report = redact(inventory(args.root))
            args.captures.mkdir(parents=True, exist_ok=True)
            out = args.captures / "inventory.txt"
            write_text_atomic(out, report)
            print(report)
            print(f"written: {out}")
            return 0
        paths = GozPaths(find_root(args.root))
        if args.uninstall:
            print(f"removed {paths.app_dir}" if uninstall(paths) else f"nothing to remove: {paths.app_dir}")
            return 0
        for path in install(paths, replace=args.replace, python=args.python, captures=args.captures,
                            import_polygroups=args.import_polygroups):
            print(f"installed {path}")
        print(f"\n'{APP_DISPLAY_NAME}' installed. In ZBrush: R next to the GoZ buttons -> choose it (README §6 T2).")
        return 0
    except ProbeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
