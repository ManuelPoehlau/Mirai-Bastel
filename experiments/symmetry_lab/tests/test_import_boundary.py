"""Import-Grenze (Handoff Slice 2 §2.6/§7): das Lab lädt nichts aus `playground/`.

Analog `tests/test_pyglet_input.py::TestInteractionStaysPygletFree`: frischer
Subprozess, alle Lab-Module importieren (inkl. Fenster/Render und `run`, dessen
`main()` dabei nicht läuft), dann `sys.modules` prüfen. Der Lab-Bootstrap legt
den Repo-Root auf sys.path — ein versehentlicher `import playground...` würde
also gelingen und hier auffallen, statt als ImportError unterzugehen.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

from symmetry_lab._paths import EXPERIMENTS_DIR

from ._pyglet_headless import import_pyglet, needs_headless

import_pyglet()  # Skip, wenn pyglet fehlt — lab_window/lab_render brauchen es.

_SCRIPT = textwrap.dedent(
    """
    import importlib, importlib.util, json, pkgutil, sys
    sys.path.insert(0, {experiments!r})
    from symmetry_lab._paths import ensure_paths
    ensure_paths()
    import pyglet
    if {headless!r}:
        pyglet.options["headless"] = True
    import symmetry_lab
    names = sorted(
        m.name for m in pkgutil.iter_modules(symmetry_lab.__path__)
        if m.name != "tests"
    )
    for name in names:
        importlib.import_module("symmetry_lab." + name)
    print(json.dumps({{
        "lab_modules": names,
        "playground_reachable": importlib.util.find_spec("playground") is not None,
        "playground_loaded": sorted(
            n for n in sys.modules if n == "playground" or n.startswith("playground.")
        ),
    }}))
    """
)


def test_no_playground_module_after_importing_all_lab_modules():
    script = _SCRIPT.format(experiments=str(EXPERIMENTS_DIR), headless=needs_headless())
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=dict(os.environ),
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])

    assert {
        "lab_window", "lab_render", "lab_dispatch", "lab_symmetry", "lab_status", "run"
    } <= set(report["lab_modules"])
    assert report["playground_reachable"], "Test wäre ohne importierbares playground wertlos"
    assert report["playground_loaded"] == []
