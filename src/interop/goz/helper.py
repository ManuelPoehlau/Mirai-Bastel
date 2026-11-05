"""ZBrush -> Mirai: what `GoZApps\\Mirai\\Edit.bat` runs after every GoZ press (AD-029 §4; E1-Q2/Q3).

    <python> -I <repo>\\src\\interop\\goz\\helper.py --root <GoZ root> --inbox <repo>\\goz\\inbox

ZBrush starts it without arguments of its own, after all `.GoZ` files are written (E1-Q4). The helper reads
`GoZ_ObjectList.txt`, snapshots every listed file by the completeness rule (`files.snapshot_object`) into
`<inbox>/staging/<ticket>/` and then drops one atomic ticket `<inbox>/<ticket>.json`. A running Mirai picks it up in
its main-loop tick (`zbrush_bridge.py`); if Mirai is not running the ticket waits for its next start - the helper never
starts Mirai (D11, Manu 2026-11-05) and never edits or deletes a ZBrush file. Stdlib only; one line per run goes to
`<inbox>/helper_log.txt`.
"""

from __future__ import annotations

import sys
from pathlib import Path

if not __package__:  # run as a script (`python -I helper.py`): import the package from src/
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

from interop.goz.files import GozPaths, find_root, new_ticket_name, snapshot_object, write_json_atomic  # noqa: E402

TICKET_VERSION = 1


def run(paths: GozPaths, inbox: Path, *, settle: float = 1.0, deadline: float = 10.0, **timing) -> Path:
    t0 = time.time_ns()
    name = new_ticket_name(t0)
    identifiers = paths.read_object_list()
    staging = inbox / "staging" / name
    snaps = [snapshot_object(ident, staging, i, settle=settle, deadline=deadline, **timing)
             for i, ident in enumerate(identifiers)]
    ticket = inbox / f"{name}.json"
    write_json_atomic(ticket, {"version": TICKET_VERSION, "created_ns": t0, "objects": [s.to_dict() for s in snaps]})
    return ticket


def _log(inbox: Path, text: str) -> None:
    try:
        inbox.mkdir(parents=True, exist_ok=True)
        with open(inbox / "helper_log.txt", "a", encoding="utf-8") as handle:
            handle.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text.rstrip("\n") + "\n")
    except OSError:
        pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root")
    parser.add_argument("--inbox", type=Path, required=True)
    parser.add_argument("--settle", type=float, default=1.0)
    parser.add_argument("zbrush_args", nargs="*")
    args = parser.parse_args(argv)
    try:
        ticket = run(GozPaths(find_root(args.root)), args.inbox, settle=args.settle)
        _log(args.inbox, f"ticket {ticket.name}")
        return 0
    except Exception:  # ZBrush shows nothing: leave a trace
        _log(args.inbox, "ERROR " + traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
