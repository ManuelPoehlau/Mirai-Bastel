"""Starts the real app (`src/main.py`) with the AD-023 stage-1 switches installed - for Manu's practical test.

    python experiments/topology_sync_stage1/run.py                      # gollum_20k, stage 1 on (V0,V2,V3,H0)
    python experiments/topology_sync_stage1/run.py --stage1 none        # same app, today's code (comparison)
    python experiments/topology_sync_stage1/run.py examples/meshes/gollum.obj --stage1 V0,V2,V3

The window title names the active switches. Everything else is `src/main.py` unchanged (keys, tools, files).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_EXPERIMENTS = Path(__file__).resolve().parents[1]
if str(_EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS))

from topology_sync_stage1._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

from topology_sync_stage1 import stage1  # noqa: E402

DEFAULT_ASSET = REPO_ROOT / "examples" / "meshes" / "gollum_20k.obj"


def main(argv: list[str]) -> None:
    spec, rest = "all", []
    it = iter(argv)
    for arg in it:
        if arg == "--stage1":
            spec = next(it)
        else:
            rest.append(arg)
    switches = stage1.install(spec)
    label = ",".join(sorted(switches)) or "aus (heutiger Code)"
    print(f"AD-023 Stufe 1: {label}")

    src_main = importlib.import_module("main")
    if Path(src_main.__file__).resolve() != REPO_ROOT / "src" / "main.py":
        raise ImportError(f"'main' is not src/main.py but {src_main.__file__}")
    create_window = src_main.create_window
    src_main.create_window = lambda caption="Mirai": create_window(f"{caption} - AD-023 Stufe 1: {label}")
    sys.argv = [str(REPO_ROOT / "src" / "main.py"), *(rest or [str(DEFAULT_ASSET)])]
    src_main.main()


if __name__ == "__main__":
    main(sys.argv[1:])
