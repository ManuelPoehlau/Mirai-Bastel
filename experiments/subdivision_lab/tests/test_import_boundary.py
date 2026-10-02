"""A10: the lab loads nothing from `playground/` or from any other `experiments/`
folder. Pattern: `experiments/viewport_shading_lab/tests/test_import_boundary.py`.

Fresh subprocess, import every lab module (incl. window, `run`, `bench` — their
`main()` does not run), then inspect `sys.modules`: by name for `playground`,
by file location for other experiment folders. The lab bootstrap puts the repo
root and `experiments/` on sys.path, so a stray import would succeed and show
up here instead of failing as ImportError.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

from subdivision_lab._paths import EXPERIMENTS_DIR

from ._pyglet_headless import import_pyglet, needs_headless

import_pyglet()  # skip if pyglet is missing — lab_window needs it

_SCRIPT = textwrap.dedent(
    """
    import importlib, importlib.util, json, os, pkgutil, sys
    sys.path.insert(0, {experiments!r})
    from subdivision_lab._paths import ensure_paths, EXPERIMENTS_DIR, LAB_DIR
    ensure_paths()
    import pyglet
    if {headless!r}:
        pyglet.options["headless"] = True
    import subdivision_lab
    names = sorted(
        m.name for m in pkgutil.iter_modules(subdivision_lab.__path__) if m.name != "tests"
    )
    for name in names:
        importlib.import_module("subdivision_lab." + name)
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
        "symmetry_lab_reachable": importlib.util.find_spec("symmetry_lab") is not None,
        "playground_loaded": sorted(
            n for n in sys.modules if n == "playground" or n.startswith("playground.")
        ),
        "foreign_experiment_modules": foreign,
        "numpy_loaded": "numpy" in sys.modules,
    }}))
    """
)


def test_no_playground_or_other_experiment_imports():
    script = _SCRIPT.format(experiments=str(EXPERIMENTS_DIR), headless=needs_headless())
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])

    assert {
        "subd", "lab_state", "lab_bindings", "lab_lines", "lab_scene", "lab_window", "run", "bench",
    } <= set(report["lab_modules"])
    assert report["playground_reachable"], "test would be worthless without importable playground"
    assert report["symmetry_lab_reachable"], "test would be worthless without importable symmetry_lab"
    assert report["playground_loaded"] == []
    assert report["foreign_experiment_modules"] == []
    assert report["numpy_loaded"] is False  # D4: pure Python
