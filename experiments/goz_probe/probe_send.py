"""E1 sender: Python -> ZBrush through the official GoZ utilities (README §2.2, §6 T4/T5).

    python -I experiments/goz_probe/probe_send.py --mesh A          # Python-written .GoZ of meshes/A.sent.json
    python -I experiments/goz_probe/probe_send.py --resend last     # a captured ZBrush file back, byte-identical

`--mesh`: the identifier comes from `GoZMakeObjectPath.exe` (the short name `E1_<id>` written to
`GoZBrush\\GoZ_ObjectPath.txt`, the tool writes the unique identifier back), unless an earlier send of the same mesh
already has one (then it is reused, so ZBrush updates the linked SubTool, as the SDK asks; `--new-identifier` forces a
new one). The file (`--style`): "sdk" = MESH `E1_A` + FLAGS 0 + float32 points + FACE4 format 1 + END; "gozmesh" = the
same named `GoZMesh_E1_A`; "zbrush" = ZBrush's own byte layout (its header text, the prefix, and its default MRGB /
MASK16 / GROUPS / CREASE blocks; reproduces a ZBrush 2022.0.8 file byte for byte). Then `GoZ_ObjectList.txt`,
`GoZ_Application.txt` (= `MiraiProbe`, before/after logged; `--keep-application` leaves it) and
`GoZBrushFromApp.exe` (mesh import; `--tmap` adds the `-tmap` flag from the SDK's texture-map demo, which
makes ZBrush export the active SubTool instead of importing the listed file - do not use for a plain mesh send).
`--axis bridge` (P1 orientation check, README §11 item 1): writes every point as `(x, -y, -z)`, the conversion the
P1 bridge uses (Mirai's Y-up frame shows in ZBrush upside down and from behind without it); short name `E1_<id>_P1`,
so it never updates a SubTool sent unflipped. `--axis raw` (default) writes the Mirai coordinates as they are.
`--groups bands` (E2, polygroups for P2): adds a GROUPS block, four bands by the face centre's height, ids 101-104
(distinct from ZBrush's random default id); short name `E1_<id>[_P1]_G`.
`--resend`: refuses when ZBrush's file changed since the capture (`--force` overrides).
`--dry-run`: writes the files, runs no program (identifier = project folder / short name).
Every step goes into `captures/<time>_send_<what>/send_log.json`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from goz_probe._paths import ensure_paths  # noqa: E402

ensure_paths()

import argparse  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

from goz_probe.goz_probe_format import STYLES, as_float32, encode_goz, parse_goz  # noqa: E402
from goz_probe.probe_common import (  # noqa: E402
    APP_FOLDER_NAME,
    DEFAULT_CAPTURES,
    DEFAULT_MESHES,
    GozPaths,
    ProbeError,
    ansi_encoding,
    find_root,
    new_capture_dir,
    read_object_list,
    read_text,
    redact,
    send_logs,
    sha256,
    write_bytes_atomic,
    write_goz_text,
    write_json_atomic,
    write_text_atomic,
)


class Steps:
    def __init__(self) -> None:
        self.items: list[dict] = []
        self.t0 = time.monotonic()

    def add(self, what: str, **data) -> None:
        item = {"t_ms": round((time.monotonic() - self.t0) * 1000, 1), "what": what, **data}
        self.items.append(item)
        print(f"[{item['t_ms']:>8.1f} ms] {what} {data if data else ''}", flush=True)


def make_object_path(paths: GozPaths, short: str, steps: Steps, *, dry_run: bool, timeout: float) -> str:
    """SDK III.9: write the short name, run GoZMakeObjectPath, wait until the file holds the unique identifier."""
    write_text_atomic(paths.object_path_file, short, encoding=ansi_encoding(), newline="")
    steps.add("wrote GoZ_ObjectPath.txt", text=short)
    if dry_run:
        identifier = str(paths.project_dir() / short)
        steps.add("dry run: identifier without GoZMakeObjectPath", identifier=identifier)
        return identifier
    exe = paths.utility("GoZMakeObjectPath")
    proc = subprocess.Popen([str(exe)], cwd=str(paths.gozbrush))
    steps.add("started GoZMakeObjectPath", pid=proc.pid, exe=str(exe))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        text = (read_text(paths.object_path_file) or "").strip()
        if text and text != short:
            steps.add("identifier received", identifier=text, returncode=proc.poll())
            return text
        time.sleep(0.05)
    raise ProbeError(f"GoZMakeObjectPath did not write an identifier within {timeout:g} s (returncode {proc.poll()})")


#: `--axis`: how a Mirai point (x, y, z) is written. "bridge" is the P1 map (self-inverse, det +1).
AXIS_MAPS = {"raw": (1.0, 1.0, 1.0), "bridge": (1.0, -1.0, -1.0)}


def band_groups(sent: dict) -> list[int]:
    """E2: ids 101-104 by the height of each face centre in the sent mesh (four equal bands)."""
    ys = [sum(sent["positions"][i][1] for i in f) / len(f) for f in sent["faces"]]
    lo, hi = min(ys), max(ys)
    return [101 + min(3, int(4 * (y - lo) / ((hi - lo) or 1.0))) for y in ys]


def previous_identifier(captures: Path, mesh_id: str, axis: str = "raw") -> str | None:
    for log in reversed(send_logs(captures)):
        if (log.get("mesh") == mesh_id and log.get("identifier") and not log.get("dry_run")
                and log.get("axis", "raw") == axis):
            return log["identifier"]
    return None


def prepare_mesh(args, paths: GozPaths, steps: Steps) -> tuple[list[str], dict]:
    sent_path = args.meshes / f"{args.mesh}.sent.json"
    if not sent_path.is_file():
        raise ProbeError(f"{sent_path} missing: run make_meshes.py first")
    sent = json.loads(sent_path.read_text(encoding="utf-8"))
    short = f"E1_{args.mesh}" + ("" if args.axis == "raw" else "_P1") + ("_G" if args.groups else "")
    identifier = None if (args.new_identifier or args.groups) else previous_identifier(args.captures, args.mesh, args.axis)
    if identifier:
        steps.add("reusing the identifier of an earlier send", identifier=identifier)
    else:
        identifier = make_object_path(paths, short, steps, dry_run=args.dry_run, timeout=args.wait_objectpath)
    signs = AXIS_MAPS[args.axis]
    points = [[as_float32(s * c) for s, c in zip(signs, p)] for p in sent["positions"]]
    groups = band_groups(sent) if args.groups == "bands" else None
    data = encode_goz(short, points, sent["faces"], style=args.style, groups=groups)
    name = parse_goz(data).name
    parse_goz(data)  # our own file must pass our strict reader
    target = Path(identifier + ".GoZ")
    write_bytes_atomic(target, data)
    steps.add("wrote .GoZ", file=str(target), bytes=len(data), sha256=sha256(data), mesh_name=name)
    steps.add("axis map", axis=args.axis, signs=signs)
    return [identifier], {"mesh": args.mesh, "identifier": identifier, "file": str(target), "sha256": sha256(data),
                          "axis": args.axis, "groups": groups}


def _capture_dir(captures: Path, which: str) -> Path:
    if which != "last":
        return Path(which)
    received = sorted(p.parent for p in captures.glob("*_receive*/receiver_log.json"))
    if not received:
        raise ProbeError(f"no receive capture in {captures}")
    return received[-1]


def prepare_resend(args, steps: Steps) -> tuple[list[str], dict]:
    cap = _capture_dir(args.captures, args.resend)
    log = json.loads((cap / "receiver_log.json").read_text(encoding="utf-8"))
    identifiers, files = [], []
    for obj in log.get("objects", []):
        copy = obj.get("copy")
        if not copy:
            continue
        copy_path = cap / Path(copy).name
        data = copy_path.read_bytes()
        target = Path(obj["identifier"] + ".GoZ")
        if target.is_file() and sha256(target.read_bytes()) != sha256(data) and not args.force:
            raise ProbeError(f"{target} changed since the capture {cap.name} (ZBrush wrote a newer file); --force to overwrite")
        if target.is_file() and sha256(target.read_bytes()) == sha256(data):
            steps.add("file already byte-identical, not rewritten", file=str(target))
        else:
            write_bytes_atomic(target, data)
            steps.add("wrote captured bytes", file=str(target), sha256=sha256(data))
        identifiers.append(obj["identifier"])
        files.append({"identifier": obj["identifier"], "file": str(target), "sha256": sha256(data)})
    if not identifiers:
        raise ProbeError(f"capture {cap} has no copied object")
    return identifiers, {"mesh": None, "resend_of": str(cap), "files": files,
                         "identifier": identifiers[0] if len(identifiers) == 1 else None}


def send(args) -> Path:
    paths = GozPaths(find_root(args.root))
    steps = Steps()
    what = args.mesh if args.mesh else "resend"
    if args.mesh:
        identifiers, info = prepare_mesh(args, paths, steps)
    else:
        identifiers, info = prepare_resend(args, steps)
    write_goz_text(paths.object_list, identifiers)
    steps.add("wrote GoZ_ObjectList.txt", lines=identifiers, read_back=read_object_list(paths.object_list))
    application_before = read_text(paths.application_file)
    if not args.keep_application:
        write_text_atomic(paths.application_file, APP_FOLDER_NAME, encoding=ansi_encoding(), newline="")
    steps.add("GoZ_Application.txt", before=application_before, after=read_text(paths.application_file))
    command = [str(paths.utility("GoZBrushFromApp"))] + (["-tmap"] if args.tmap else [])
    if args.dry_run:
        steps.add("dry run: not started", command=command)
    else:
        proc = subprocess.Popen(command, cwd=str(paths.gozbrush))
        steps.add("started GoZBrushFromApp", pid=proc.pid, command=command)
        try:
            steps.add("GoZBrushFromApp exited", returncode=proc.wait(timeout=args.wait_fromapp))
        except subprocess.TimeoutExpired:
            steps.add(f"GoZBrushFromApp still running after {args.wait_fromapp:g} s (left alone)")
    cap = new_capture_dir(args.captures, f"send_{what}")
    write_json_atomic(cap / "send_log.json", redact({**info, "dry_run": args.dry_run, "style": args.style,
                                                    "command": command, "steps": steps.items}))
    print(f"send log: {cap / 'send_log.json'}")
    return cap


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--mesh", choices=("A", "B", "C"))
    what.add_argument("--resend", metavar="last|CAPTURE_DIR")
    parser.add_argument("--root")
    parser.add_argument("--meshes", type=Path, default=DEFAULT_MESHES)
    parser.add_argument("--captures", type=Path, default=DEFAULT_CAPTURES)
    parser.add_argument("--style", choices=STYLES, default="sdk",
                        help="sdk: the SDK's minimal file; gozmesh: + name prefix GoZMesh_; zbrush: ZBrush's own layout")
    parser.add_argument("--axis", choices=tuple(AXIS_MAPS), default="raw",
                        help="raw: Mirai coordinates as they are; bridge: (x, -y, -z), the P1 conversion (README §11)")
    parser.add_argument("--groups", choices=("bands",), help="E2: send four polygroups (ids 101-104)")
    parser.add_argument("--new-identifier", action="store_true")
    parser.add_argument("--keep-application", action="store_true")
    parser.add_argument("--tmap", action="store_true",
                        help="append the SDK-demo `-tmap` flag (texture-map round-trip; makes ZBrush export the "
                             "active SubTool instead of importing - not what a plain mesh send needs)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wait-objectpath", type=float, default=10.0)
    parser.add_argument("--wait-fromapp", type=float, default=15.0)
    args = parser.parse_args(argv)
    try:
        send(args)
        return 0
    except ProbeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
