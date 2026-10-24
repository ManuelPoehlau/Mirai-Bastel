"""The lab loads nothing from `playground/` or from any other `experiments/` folder. Pattern: the former
`experiments/subdivision_lab/tests/test_import_boundary.py` (rebuilt, not imported).

Fresh subprocess, import every lab module (incl. the window module and `run` — `main()` does not
run), then inspect `sys.modules`: by name for `playground`, by file location for other experiment
folders. The lab bootstrap puts the repo root and `experiments/` on sys.path, so a stray import
would succeed and show up here instead of failing as ImportError.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

from morph_lab._paths import EXPERIMENTS_DIR

from ._pyglet_headless import import_pyglet, needs_headless

import_pyglet()  # skip if pyglet is missing — lab_app_window needs it

_SCRIPT = textwrap.dedent(
    """
    import importlib, importlib.util, json, os, pkgutil, sys
    sys.path.insert(0, {experiments!r})
    from morph_lab._paths import ensure_paths, EXPERIMENTS_DIR, LAB_DIR
    ensure_paths()
    import pyglet
    if {headless!r}:
        pyglet.options["headless"] = True
    import morph_lab
    names = sorted(m.name for m in pkgutil.iter_modules(morph_lab.__path__) if m.name != "tests")
    for name in names:
        importlib.import_module("morph_lab." + name)
    experiments_dir = str(EXPERIMENTS_DIR) + os.sep
    lab_dir = str(LAB_DIR) + os.sep
    foreign = sorted(
        n for n, m in list(sys.modules.items())
        if (getattr(m, "__file__", None) or "").startswith(experiments_dir)
        and not (m.__file__).startswith(lab_dir)
    )
    print(json.dumps({{
        "lab_modules": names,
        "playground_reachable": importlib.util.find_spec("playground") is not None,
        "other_lab_reachable": importlib.util.find_spec("knife_oracle") is not None,
        "playground_loaded": sorted(
            n for n in sys.modules if n == "playground" or n.startswith("playground.")
        ),
        "foreign_experiment_modules": foreign,
    }}))
    """
)


def test_no_playground_or_other_experiment_imports():
    script = _SCRIPT.format(experiments=str(EXPERIMENTS_DIR), headless=needs_headless())
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])

    assert {"_paths", "morph", "lab_scene", "lab_app", "lab_app_window", "run"} <= set(report["lab_modules"])
    assert report["playground_reachable"], "test would be worthless without importable playground"
    assert report["other_lab_reachable"], "test would be worthless without an importable other experiment"
    assert report["playground_loaded"] == []
    assert report["foreign_experiment_modules"] == []
