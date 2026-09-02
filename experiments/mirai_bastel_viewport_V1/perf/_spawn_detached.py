"""Startet einen Benchmark als getrennten Prozess (DETACHED_PROCESS).

Grund: Die Command-Ausfuehrung der Agent-Umgebung wartet auf EOF der
Ausgabepipes; ein lang laufender Benchmark wuerde den Aufruf blockieren.
Der Spawner kehrt sofort zurueck, stdout/stderr landen in Dateien.

Aufruf:
    python perf/_spawn_detached.py <output_base> <command...>

Erzeugt <output_base>.out.txt und <output_base>.err.txt im perf-Ordner.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000


def main() -> None:
    base = Path(sys.argv[1]).resolve()
    command = sys.argv[2:]
    out_path = base.with_suffix(".out.txt")
    err_path = base.with_suffix(".err.txt")
    process = subprocess.Popen(
        command,
        cwd=str(base.parent.parent),
        stdout=open(out_path, "w", encoding="utf-8"),
        stderr=open(err_path, "w", encoding="utf-8"),
        creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW,
    )
    print(f"STARTED pid={process.pid}")
    print(f"out: {out_path}")
    print(f"err: {err_path}")


if __name__ == "__main__":
    main()
