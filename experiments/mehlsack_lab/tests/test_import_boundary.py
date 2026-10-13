"""Import boundary (handoff §6, E3): the lab loads `src` modules plus exactly one `playground`
module — `playground.topology_tools.loop_ring` — and nothing from any other `experiments/`
folder. Nothing imports the lab. Pattern: `subdivision_lab/tests/test_import_boundary.py`.

Fresh subprocess, import every lab module (incl. window and `run`; `main()` does not run),
then inspect `sys.modules`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from mehlsack_lab._paths import EXPERIMENTS_DIR, REPO_ROOT

from ._pyglet_headless import import_pyglet, needs_headless

import_pyglet()  # skip if pyglet is missing — lab_window needs it

ALLOWED_PLAYGROUND = {"playground", "playground.topology_tools", "playground.topology_tools.loop_ring"}

_SCRIPT = textwrap.dedent(
    """
    import importlib, importlib.util, json, os, pkgutil, sys
    sys.path.insert(0, {experiments!r})
    from mehlsack_lab._paths import ensure_paths, EXPERIMENTS_DIR, LAB_DIR
    ensure_paths()
    import pyglet
    if {headless!r}:
        pyglet.options["headless"] = True
    import mehlsack_lab
    names = sorted(m.name for m in pkgutil.iter_modules(mehlsack_lab.__path__) if m.name != "tests")
    for name in names:
        importlib.import_module("mehlsack_lab." + name)
    experiments_dir = str(EXPERIMENTS_DIR) + os.sep
    lab_dir = str(LAB_DIR) + os.sep
    foreign = sorted(
        n for n, m in list(sys.modules.items())
        if (getattr(m, "__file__", None) or "").startswith(experiments_dir)
        and not (m.__file__).startswith(lab_dir)
    )
    print(json.dumps({{
        "lab_modules": names,
        "playground_loaded": sorted(
            n for n in sys.modules if n == "playground" or n.startswith("playground.")
        ),
        "foreign_experiment_modules": foreign,
        "numpy_loaded": "numpy" in sys.modules,
    }}))
    """
)


def test_only_src_and_loop_ring():
    script = _SCRIPT.format(experiments=str(EXPERIMENTS_DIR), headless=needs_headless())
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert {
        "box", "targets", "signed_curve", "signed_influence", "signed_ops", "edit_session",
        "lab_bands", "lab_preview", "curve_panel", "lab_bindings", "lab_state", "lab_scene", "lab_window",
        "lab_selection", "lab_pointer", "run",
    } <= set(report["lab_modules"])
    assert set(report["playground_loaded"]) == ALLOWED_PLAYGROUND
    assert report["foreign_experiment_modules"] == []
    assert report["numpy_loaded"] is False


def test_nothing_imports_the_lab():
    offenders = []
    for root in ("src", "playground", "tests", "examples", "experiments"):
        for path in (REPO_ROOT / root).rglob("*.py"):
            if "mehlsack_lab" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "mehlsack_lab" in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
