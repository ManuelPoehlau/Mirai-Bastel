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


def process_ticket(ticket: Path, now_ns: int | None = None) -> dict:
    data = json.loads(ticket.read_text(encoding="utf-8"))
    now_ns = time.time_ns() if now_ns is None else now_ns
    results = []
    for obj in data.get("objects", []):
        copy = obj.get("copy")
        ok = False
        if copy and Path(copy).is_file() and obj.get("sha256"):
            ok = sha256(Path(copy).read_bytes()) == obj["sha256"]
        results.append({"identifier": obj.get("identifier"), "hash_ok": ok})
    return {
        "ticket": ticket.name,
        "objects": len(results),
        "all_ok": bool(results) and all(r["hash_ok"] for r in results),
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
               f"{result['objects']} object(s), hashes {'ok' if result['all_ok'] else 'NOT ok'}, "
               f"{result['latency_ms']:.0f} ms after the receiver started")
        )
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
        done.mkdir(exist_ok=True)
        os.replace(ticket, done / ticket.name)
        handled.append(result)
    return handled


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
    args = parser.parse_args(argv)
    try:
        return run(args.inbox, args.poll, args.max_seconds)
    except ProbeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
