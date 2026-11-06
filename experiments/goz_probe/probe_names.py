"""T10 (AD-029 §3, 2026-11-06): what lies in ZBrush's GoZ project folder, and who wrote it. Reads only.

    python -I experiments/goz_probe/probe_names.py                 # the listing (= `dir GoZProjects\\Default`, with
                                                                   #   the writer and the mesh name of every .GoZ)
    python -I experiments/goz_probe/probe_names.py --make Kopf     # optional: what GoZMakeObjectPath answers now

Per file of `GoZProjects\\Default` (or what `GoZ_ProjectPath.txt` names): size, last write, and for a `.GoZ` the
header text (ZBrush writes ` 1.0 ZBrush GoZ Binary`, Mirai ` 1.0 Mirai GoZ`, the probe its own), the MESH name and the
counts; then Mirai's name registry (`goz/manifests/names.json`). `--make NAME` writes `NAME` into
`GoZBrush\\GoZ_ObjectPath.txt` and runs `GoZMakeObjectPath.exe`, as every GoZ app does - the one write, only on request;
Mirai itself no longer asks it. Output: the screen and `captures/<time>_names/names_log.json`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from goz_probe._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

import argparse  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

from goz_probe.goz_probe_format import GozFormatError, parse_goz  # noqa: E402
from goz_probe.probe_common import (  # noqa: E402
    DEFAULT_CAPTURES,
    GozPaths,
    ProbeError,
    ansi_encoding,
    find_root,
    new_capture_dir,
    read_text,
    redact,
    write_json_atomic,
    write_text_atomic,
)


def describe(path: Path) -> dict:
    st = path.stat()
    item = {"name": path.name, "bytes": st.st_size, "written": time.strftime("%Y-%m-%d %H:%M:%S",
                                                                            time.localtime(st.st_mtime))}
    if path.suffix.lower() == ".goz":
        data = path.read_bytes()
        item["header"] = data[4:32].split(b"\0")[0].decode("latin-1", errors="replace").strip(" .")
        try:
            goz = parse_goz(data)
            item.update(mesh=goz.name, points=len(goz.points), faces=len(goz.faces))
        except GozFormatError as exc:
            item["error"] = str(exc)
    return item


def make_object_path(paths: GozPaths, short: str, timeout: float = 10.0) -> dict:
    before = read_text(paths.object_path_file)
    write_text_atomic(paths.object_path_file, short, encoding=ansi_encoding(), newline="")
    proc = subprocess.Popen([str(paths.utility("GoZMakeObjectPath"))], cwd=str(paths.gozbrush))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = (read_text(paths.object_path_file) or "").strip()
        if text and text != short:
            return {"asked": short, "answer": text, "before": before, "returncode": proc.poll()}
        time.sleep(0.05)
    return {"asked": short, "answer": None, "before": before, "returncode": proc.poll()}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root")
    parser.add_argument("--make", action="append", default=[], metavar="NAME")
    parser.add_argument("--captures", type=Path, default=DEFAULT_CAPTURES)
    args = parser.parse_args(argv)
    try:
        paths = GozPaths(find_root(args.root))
    except ProbeError as exc:
        print(exc)
        return 1
    project = paths.project_dir()
    files = sorted((describe(p) for p in project.iterdir() if p.is_file()), key=lambda i: i["name"].lower()) \
        if project.is_dir() else []
    registry = REPO_ROOT / "goz" / "manifests" / "names.json"
    try:
        names = json.loads(registry.read_text(encoding="utf-8")).get("entries", [])
    except (OSError, ValueError):
        names = None
    made = [make_object_path(paths, name) for name in args.make]
    config = read_text(paths.gozbrush / "GoZ_Config.txt") or ""
    print("GoZ_Config.txt: " + " | ".join(line.strip() for line in config.splitlines() if line.strip()))
    print(f"{project}  ({len(files)} files)")
    for i in files:
        extra = f"  [{i.get('header', '')}] mesh {i.get('mesh')!r} {i.get('points')}/{i.get('faces')}" \
            if "header" in i else ""
        print(f"  {i['written']}  {i['bytes']:>10}  {i['name']}{extra}{'  ' + i['error'] if 'error' in i else ''}")
    print(f"Mirai names ({registry}):" if names is not None else f"Mirai names: none ({registry})")
    for e in names or []:
        print(f"  {e.get('stem')!r:30} object {e.get('object_id')} target {e.get('layer')}  former {e.get('former')}"
              f"  scene {'yes' if e.get('scene') else 'unsaved'}")
    for m in made:
        print(f"GoZMakeObjectPath {m['asked']!r} -> {m['answer']!r}")
    out = new_capture_dir(args.captures, "names")
    write_json_atomic(out / "names_log.json", redact({"project": str(project), "goz_config": config, "files": files, "mirai_names": names,
                                                      "make": made}))
    print(f"-> {out / 'names_log.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
