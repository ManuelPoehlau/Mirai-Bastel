"""Starts the real app (`src/main.py`) with the stage-2 Delete prototype installed - for Manu's practical test.

    python experiments/topology_stage2_delete/run.py                       # gollum_20k, all (stage 1 + H1,V1,GPU)
    python experiments/topology_stage2_delete/run.py --config stage1       # same app, stage 1 only (comparison)
    python experiments/topology_stage2_delete/run.py --config none         # same app, today's code
    python experiments/topology_stage2_delete/run.py examples/meshes/gollum.obj

Only Delete (Entf, vertex / edge / face mode, no symmetry definition) and its Undo / Redo take the stage-2 path;
hover and click in face and vertex mode pick on the GPU. Everything else is stage 1 (`--config all`) or
today's code (`--config none`). The window title names the configuration.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_EXPERIMENTS = Path(__file__).resolve().parents[1]
if str(_EXPERIMENTS) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS))

from topology_stage2_delete._paths import REPO_ROOT, ensure_paths  # noqa: E402

ensure_paths()

from topology_stage2_delete import stage2  # noqa: E402

DEFAULT_ASSET = REPO_ROOT / "examples" / "meshes" / "gollum_20k.obj"


def main(argv: list[str]) -> None:
    spec, rest = "all", []
    it = iter(argv)
    for arg in it:
        if arg == "--config":
            spec = next(it)
        else:
            rest.append(arg)
    stage2.install(spec)
    label = stage2.label(spec)
    print(f"AD-023 Stufe 2 (nur Delete) + AD-022: {label}")

    src_main = importlib.import_module("main")
    if Path(src_main.__file__).resolve() != REPO_ROOT / "src" / "main.py":
        raise ImportError(f"'main' is not src/main.py but {src_main.__file__}")
    create_window = src_main.create_window
    src_main.create_window = lambda caption="Mirai": create_window(f"{caption} - Stufe 2 Delete: {label}")
    sys.argv = [str(REPO_ROOT / "src" / "main.py"), *(rest or [str(DEFAULT_ASSET)])]
    src_main.main()


if __name__ == "__main__":
    main(sys.argv[1:])
