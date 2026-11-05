"""E1 receiver: what ZBrush launches through `GoZApps\\MiraiProbe\\Edit.bat` after a GoZ (README §5, §6 T2/T3, §7).

Records the launch (time, arguments, working directory, the chain of parent processes), copies every listed `.GoZ`
file into `captures/<time>_receive/` (it never edits, moves or deletes ZBrush's files), measures whether the files
were complete when it started (strict parse, exclusive open, unchanged after a wall-clock settle period), compares
each copy with the mesh it was sent as, and - if a listener is running - drops an atomic ticket into `inbox/`. It
starts nothing and exits within about `--settle` + 1 s.

Privacy: the user profile path and the user name are replaced by `%USERPROFILE%` / `%USERNAME%` in everything it
writes (the captures are committed to a public repository).

    python -I experiments/goz_probe/probe_receiver.py [--root DIR] [-- <arguments ZBrush passed>]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from goz_probe._paths import ensure_paths  # noqa: E402

ensure_paths()

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

from goz_probe.goz_probe_format import GozFormatError, dump, parse_goz  # noqa: E402
from goz_probe.probe_common import (  # noqa: E402
    DEFAULT_CAPTURES,
    DEFAULT_INBOX,
    DEFAULT_MESHES,
    INVALID_HANDLE,
    IS_WINDOWS,
    GozPaths,
    analyse,
    analysis_lines,
    exclusive_open,
    find_root,
    kernel32,
    load_sent,
    match_sent,
    new_capture_dir,
    process_alive,
    redact,
    python_info,
    read_object_list,
    read_pff,
    read_text,
    send_logs,
    sha256,
    stat_record,
    timestamp,
    write_bytes_atomic,
    write_json_atomic,
    write_text_atomic,
)

LOCK_NAME = "listener.lock"
ENV_KEYS = ("OS", "PROCESSOR_ARCHITECTURE", "PUBLIC", "SystemRoot")


def process_chain(depth: int = 5) -> list[dict]:
    """Windows: this process and its ancestors (pid, executable name) - shows whether ZBrush runs Edit.bat directly."""
    if not IS_WINDOWS:
        return [{"pid": os.getpid(), "exe": Path(sys.executable).name}, {"pid": os.getppid(), "exe": "?"}]
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG), ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    k = kernel32()
    k.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k.Process32FirstW.restype = wintypes.BOOL
    k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k.Process32NextW.restype = wintypes.BOOL
    snapshot = k.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snapshot is None or snapshot == INVALID_HANDLE:
        return [{"pid": os.getpid(), "exe": "(no process snapshot)"}]
    table: dict[int, tuple[int, str]] = {}
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        ok = k.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            table[entry.th32ProcessID] = (entry.th32ParentProcessID, entry.szExeFile)
            ok = k.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        k.CloseHandle(snapshot)
    chain, pid = [], os.getpid()
    for _ in range(depth):
        if pid not in table:
            chain.append({"pid": pid, "exe": "(exited or unknown)"})
            break
        parent, exe = table[pid]
        chain.append({"pid": pid, "exe": exe})
        pid = parent
    return chain


def _safe(function, *args):
    """Windows-only diagnostics must never stop the receiver: an error becomes the recorded value."""
    try:
        return function(*args)
    except Exception as exc:  # ctypes and OS errors alike
        return f"error: {type(exc).__name__}: {exc}"


def _listener_pid(inbox: Path):
    try:
        return int(json.loads((inbox / LOCK_NAME).read_text(encoding="utf-8"))["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def receive(
    paths: GozPaths,
    *,
    captures: Path = DEFAULT_CAPTURES,
    inbox: Path = DEFAULT_INBOX,
    meshes: Path = DEFAULT_MESHES,
    settle: float = 1.0,
    launched_by: str = "manual",
    raw_args=(),
) -> Path:
    t0 = time.time_ns()
    mono0 = time.monotonic()
    cap = new_capture_dir(captures, "receive", t0)
    log: dict = {
        "t0_ns": t0,
        "t0_local": timestamp(t0),
        "launched_by": launched_by,
        "argv": sys.argv,
        "zbrush_args": list(raw_args),
        "cwd": os.getcwd(),
        "pid": os.getpid(),
        "process_chain": _safe(process_chain),
        "env": {k: os.environ.get(k) for k in ENV_KEYS if os.environ.get(k) is not None},
        "env_names_goz": sorted(k for k in os.environ if any(s in k.upper() for s in ("ZBRUSH", "GOZ", "PIXOLOGIC", "MAXON"))),
        "python": python_info(),
        "root": str(paths.root),
        "settle_s": settle,
    }
    texts = {}
    for path in (paths.object_list, paths.application_file, paths.project_path_file, paths.object_path_file):
        texts[path.name] = {"stat": stat_record(path), "text": read_text(path)}
    log["gozbrush_texts"] = texts
    if texts["GoZ_ObjectList.txt"]["text"] is not None:
        write_text_atomic(cap / "GoZ_ObjectList.txt", texts["GoZ_ObjectList.txt"]["text"], newline="")
    log["app_config"] = read_pff(paths.app_dir / "GoZ_Config.txt")
    extension = read_pff(paths.app_dir / "GoZ_Info.txt").get("EXTENSION", ".GoZ") or ".GoZ"
    objects = []
    for n, identifier in enumerate(read_object_list(paths.object_list)):
        source = Path(identifier + extension)
        record: dict = {"identifier": identifier, "file": str(source), "stat_at_start": stat_record(source)}
        if record["stat_at_start"]["exists"]:
            record["ms_since_write_at_start"] = (t0 - record["stat_at_start"]["mtime_ns"]) / 1e6
            record["exclusive_open"] = _safe(exclusive_open, source)
            try:
                data = source.read_bytes()
            except OSError as exc:
                record["read_error"] = str(exc)
                data = None
            if data is not None:
                record["sha256_at_start"] = sha256(data)
                copy = cap / f"{n:02d}_{source.name}"
                write_bytes_atomic(copy, data)
                record["copy"] = str(copy)
        objects.append(record)
    remaining = settle - (time.monotonic() - mono0)
    if remaining > 0:
        time.sleep(remaining)
    for record in objects:
        if "sha256_at_start" not in record:
            continue
        source = Path(record["file"])
        record["stat_after_settle"] = stat_record(source)
        try:
            record["sha256_after_settle"] = sha256(source.read_bytes())
        except OSError as exc:
            record["sha256_after_settle"] = f"read error: {exc}"
        record["changed_after_settle"] = (
            record["sha256_after_settle"] != record["sha256_at_start"]
            or record["stat_after_settle"] != record["stat_at_start"]
        )
    sent = load_sent(meshes) if meshes.is_dir() else {}
    logs = send_logs(captures)
    report = [f"E1 receive {timestamp(t0)}  launched_by={launched_by}  objects={len(objects)}", ""]
    for record in objects:
        report.append(f"=== {record['identifier']}")
        if "copy" not in record:
            report.append(f"not read: {record.get('read_error') or 'file missing'}")
            record["complete_at_start"] = False
            continue
        try:
            goz = parse_goz(Path(record["copy"]).read_bytes())
        except GozFormatError as exc:
            record["complete_at_start"] = False
            record["format_error"] = str(exc)
            report.append(f"FORMAT ERROR (fails closed): {exc}")
            continue
        record["complete_at_start"] = True
        record["summary"] = {
            "name": goz.name, "flags": goz.flags, "flag_names": goz.flag_names(), "subdiv": goz.subdiv,
            "points": len(goz.points), "faces": len(goz.faces), "face_types": goz.face_type_counts(),
            "header_text": goz.header_text.decode("latin-1"), "blocks": [(b.tag, b.name, b.size, b.count) for b in goz.blocks],
            "anomalies": goz.anomalies,
        }
        report.append(dump(goz).rstrip("\n"))
        match, how = match_sent(goz, record["identifier"], sent, logs)
        record["matched_sent"] = {"id": match["id"] if match else None, "by": how}
        if match is not None:
            result = analyse(goz, match)
            record["analysis"] = result
            report.append(f"matched sent mesh {match['id']} by {how}")
            report.extend(analysis_lines(result))
        else:
            report.append("no sent mesh matched (run make_meshes.py first, or a new SubTool)")
        report.append(
            f"Datei fertig beim Start: complete_at_start={record['complete_at_start']}, "
            f"exclusive_open={record.get('exclusive_open')}, changed_after_{settle:g}s={record.get('changed_after_settle')}, "
            f"geschrieben {record.get('ms_since_write_at_start', 0):.1f} ms vor dem Start"
        )
        report.append("")
    log["objects"] = objects
    pid = _listener_pid(inbox)
    if pid is not None and process_alive(pid):
        ticket = inbox / f"ticket_{t0}_{os.getpid()}.json"
        # Not redacted: a ticket is machine data the listener must resolve (inbox/ is never committed). Redacting it made
        # every copy path unfindable on Windows (E1 run 2026-11-05: "hashes NOT ok").
        write_json_atomic(ticket, {
            "t0_ns": t0, "capture": str(cap),
            "objects": [{"identifier": r["identifier"], "copy": r.get("copy"), "sha256": r.get("sha256_at_start")} for r in objects],
        })
        log["listener"] = {"pid": pid, "alive": True, "ticket": str(ticket)}
        report.append(f"listener pid {pid} alive: ticket {ticket.name} written")
    else:
        log["listener"] = {"pid": pid, "alive": False}
        report.append("no listener running: no ticket (nothing is started)")
    log["duration_ms"] = (time.monotonic() - mono0) * 1000
    write_json_atomic(cap / "receiver_log.json", redact(log))
    write_text_atomic(cap / "dump.txt", redact("\n".join(report) + "\n"))
    print(redact("\n".join(report)))
    print(f"capture: {cap}")
    return cap


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root")
    parser.add_argument("--captures", type=Path, default=DEFAULT_CAPTURES)
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--meshes", type=Path, default=DEFAULT_MESHES)
    parser.add_argument("--settle", type=float, default=1.0, help="wall-clock seconds before the re-check (README §7)")
    parser.add_argument("--launched-by", default="manual")
    parser.add_argument("zbrush_args", nargs="*", help="whatever ZBrush passed to Edit.bat (after --)")
    args = parser.parse_args(argv)
    try:
        receive(
            GozPaths(find_root(args.root)), captures=args.captures, inbox=args.inbox, meshes=args.meshes,
            settle=args.settle, launched_by=args.launched_by, raw_args=args.zbrush_args,
        )
        return 0
    except Exception:  # the receiver must leave a trace whatever happens; ZBrush shows nothing
        text = redact(traceback.format_exc())
        args.captures.mkdir(parents=True, exist_ok=True)
        (args.captures / f"receiver_error_{timestamp()}.txt").write_text(text, encoding="utf-8")
        print(text, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
