"""E1 listener: a stand-in for a running Mirai (README §2.4, §6 T3).

Holds `inbox/listener.lock` (its PID), polls `inbox/` for tickets the receiver writes, verifies each ticket's copies
against their sha256, prints the latency from the receiver's start to the pick-up and moves the ticket to
`inbox/done/`. Only one listener at a time; a stale lock (dead PID) is replaced. Ctrl+C ends it and removes the lock.
Files ending in `.tmp` are never read (the receiver writes tickets atomically: tmp file, then rename).

    python -I experiments/goz_probe/probe_listener.py [--inbox DIR] [--poll 0.25]
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

from goz_probe.probe_common import DEFAULT_INBOX, ProbeError, process_alive, sha256, timestamp  # noqa: E402
from goz_probe.probe_receiver import LOCK_NAME  # noqa: E402


def acquire_lock(inbox: Path) -> Path:
    inbox.mkdir(parents=True, exist_ok=True)
    lock = inbox / LOCK_NAME
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                pid = int(json.loads(lock.read_text(encoding="utf-8"))["pid"])
            except (OSError, ValueError, KeyError, TypeError):
                pid = -1
            if process_alive(pid):
                raise ProbeError(f"another listener is running (pid {pid}); {lock}") from None
            lock.unlink(missing_ok=True)  # stale
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "started_ns": time.time_ns()}, handle)
        return lock
    raise ProbeError(f"cannot take {lock}")


def release_lock(lock: Path) -> None:
    try:
        if int(json.loads(lock.read_text(encoding="utf-8"))["pid"]) == os.getpid():
            lock.unlink()
    except (OSError, ValueError, KeyError, TypeError):
        pass


def check_copy(copy, expected) -> str:
    """"ok", "no hash", "copy not found: <path>" or "hash mismatch". `%USERPROFILE%` in a path (tickets written before
    the 2026-11-05 fix were redacted) is expanded, so those tickets can still be checked (`--recheck-done`)."""
    if not expected:
        return "no hash"
    if not copy:
        return "no copy"
    path = Path(os.path.expandvars(copy))
    if not path.is_file():
        return f"copy not found: {copy}"
    return "ok" if sha256(path.read_bytes()) == expected else "hash mismatch"


def process_ticket(ticket: Path, now_ns: int | None = None) -> dict:
    data = json.loads(ticket.read_text(encoding="utf-8"))
    now_ns = time.time_ns() if now_ns is None else now_ns
    results = []
    for obj in data.get("objects", []):
        status = check_copy(obj.get("copy"), obj.get("sha256"))
        results.append({"identifier": obj.get("identifier"), "status": status, "hash_ok": status == "ok"})
    return {
        "ticket": ticket.name,
        "objects": len(results),
        "all_ok": bool(results) and all(r["hash_ok"] for r in results),
        "problems": sorted({r["status"] for r in results if r["status"] != "ok"}),
        "latency_ms": (now_ns - int(data["t0_ns"])) / 1e6,
        "results": results,
    }


def poll_once(inbox: Path, log) -> list[dict]:
    done = inbox / "done"
    handled = []
    for ticket in sorted(inbox.glob("ticket_*.json")):
        try:
            result = process_ticket(ticket)
        except (OSError, ValueError, KeyError) as exc:
            result = {"ticket": ticket.name, "error": str(exc)}
        line = (
            f"{timestamp()} ticket {result['ticket']}: "
            + (f"ERROR {result['error']}" if "error" in result else
               f"{result['objects']} object(s), hashes {'ok' if result['all_ok'] else 'NOT ok ' + str(result['problems'])}, "
               f"{result['latency_ms']:.0f} ms after the receiver started")
        )
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
        done.mkdir(exist_ok=True)
        os.replace(ticket, done / ticket.name)
        handled.append(result)
    return handled


def recheck_done(inbox: Path) -> int:
    """Checks the tickets in inbox/done/ again (hashes only; the latency stays the one printed at pick-up)."""
    tickets = sorted((inbox / "done").glob("ticket_*.json"))
    for ticket in tickets:
        result = process_ticket(ticket)
        state = "ok" if result["all_ok"] else f"NOT ok {result['problems']}"
        print(f"{ticket.name}: {result['objects']} object(s), hashes {state}")
    if not tickets:
        print(f"no tickets in {inbox / 'done'}")
    return 0


def run(inbox: Path, poll: float, max_seconds: float | None = None) -> int:
    lock = acquire_lock(inbox)
    print(f"listener pid {os.getpid()} waiting for tickets in {inbox} (Ctrl+C to stop)", flush=True)
    start = time.monotonic()
    try:
        with open(inbox / "listener_log.txt", "a", encoding="utf-8") as log:
            log.write(f"{timestamp()} listener start pid {os.getpid()}\n")
            while max_seconds is None or time.monotonic() - start < max_seconds:
                poll_once(inbox, log)
                time.sleep(poll)
    except KeyboardInterrupt:
        print("stopped", flush=True)
    finally:
        release_lock(lock)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--poll", type=float, default=0.25)
    parser.add_argument("--max-seconds", type=float, default=None, help="stop after this long (tests)")
    parser.add_argument("--recheck-done", action="store_true", help="check the tickets in inbox/done/ again and exit")
    args = parser.parse_args(argv)
    if args.recheck_done:
        return recheck_done(args.inbox)
    try:
        return run(args.inbox, args.poll, args.max_seconds)
    except ProbeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
