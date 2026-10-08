"""Import boundary: the experiment loads nothing from `playground/` (AD-010 precedent)
and nothing from other experiments. Fresh subprocess, import every module, inspect
`sys.modules` (pattern of `symmetry_lab/tests/test_import_boundary.py`, not imported)."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

from soft_selection._paths import EXPERIMENTS_DIR

MODULES = ("_paths", "influence", "weighted_ops", "probe_cost")


def test_no_playground_or_foreign_experiment_imports():
    script = textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {str(EXPERIMENTS_DIR)!r})
        from soft_selection._paths import ensure_paths
        ensure_paths()
        import importlib
        for name in {MODULES!r}:
            importlib.import_module("soft_selection." + name)
        print(json.dumps(sorted(sys.modules)))
        """
    )
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    ).stdout
    loaded = json.loads(out.strip().splitlines()[-1])
    tops = {name.split(".")[0] for name in loaded}
    assert "playground" not in tops
    assert not tops & {"symmetry_lab", "mirai_bastel_integration_lab", "rigging_skinning_morphing"}
    assert "pyglet" not in tops  # headless: no window stack
